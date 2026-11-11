from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.commerce.models import Subscription


class EntitlementService:
    """Use verified, currently active subscription snapshots to resolve paid benefits."""
    def __init__(self, db: Session):
        self.db = db
        self._exercise_permissions: dict[str, tuple[set[str], bool]] = {}

    def current(self, client_id: str, at: datetime | None = None) -> dict[str, bool | int]:
        now = at or datetime.now(UTC)
        subscriptions = self.db.scalars(select(Subscription).where(Subscription.client_id == client_id, Subscription.status.in_(["ACTIVE", "CANCEL_AT_PERIOD_END"]), Subscription.current_period_start <= now, Subscription.current_period_end > now)).all()
        result: dict[str, bool | int] = {}
        for subscription in subscriptions:
            for key, value in subscription.entitlements.items():
                if isinstance(value, bool):
                    result[key] = bool(result.get(key)) or value
                elif isinstance(value, int):
                    result[key] = max(int(result.get(key, 0)), value)
        from app.modules.commerce.models import EntitlementGrant
        for grant in self.db.scalars(select(EntitlementGrant).where(
            EntitlementGrant.user_id == client_id, EntitlementGrant.resource_id == '',
            EntitlementGrant.starts_at <= now, EntitlementGrant.revoked_at.is_(None),
            (EntitlementGrant.expires_at.is_(None)) | (EntitlementGrant.expires_at > now))):
            result[grant.key] = True
        return result

    def grants(self, user_id: str):
        from app.modules.commerce.models import EntitlementGrant
        now = datetime.now(UTC)
        return self.db.scalars(select(EntitlementGrant).where(EntitlementGrant.user_id == user_id,
            EntitlementGrant.starts_at <= now, EntitlementGrant.revoked_at.is_(None),
            (EntitlementGrant.expires_at.is_(None)) | (EntitlementGrant.expires_at > now))).all()

    def permits(self, user_id: str, key: str, resource_id: str = '') -> bool:
        if not resource_id and self.current(user_id).get(key) is True:
            return True
        return any(grant.key == key and grant.resource_id == resource_id for grant in self.grants(user_id))

    def assignment_active(self, assignment) -> bool:
        from app.modules.commerce.models import EntitlementGrant
        if assignment.status != 'ACTIVE':
            return False
        grants = self.db.scalars(select(EntitlementGrant).where(EntitlementGrant.source_id == assignment.id,
                                  EntitlementGrant.user_id == assignment.client_id, EntitlementGrant.key == 'program_access')).all()
        if not grants:
            return True  # Existing explicit coach assignments remain legitimate manual access.
        active_ids = {grant.id for grant in self.grants(assignment.client_id)}
        return any(grant.id in active_ids for grant in grants)

    def exercise_ids(self, user_id: str) -> set[str]:
        from app.modules.coaching.models import ProgramAssignment
        result: set[str] = set()
        for assignment in self.db.scalars(select(ProgramAssignment).where(ProgramAssignment.client_id == user_id, ProgramAssignment.status == 'ACTIVE')):
            if self.assignment_active(assignment):
                result.update(item['exercise_id'] for workout in assignment.snapshot.get('workouts', [])
                              for item in workout.get('exercises', []) if item.get('exercise_id'))
        return result

    def program_allowed(self, user_id: str, program_id: str) -> bool:
        from app.modules.coaching.models import ProgramAssignment
        if self.permits(user_id, 'program_access', program_id):
            return True
        return any(self.assignment_active(item) for item in self.db.scalars(select(ProgramAssignment).where(
            ProgramAssignment.client_id == user_id, ProgramAssignment.program_id == program_id, ProgramAssignment.status == 'ACTIVE')))

    def exercise_policy(self, user_id: str) -> tuple[set[str], bool]:
        # One service instance lives only within its current request. Reuse the
        # policy across a page of exercises, never across requests or revocations.
        if user_id not in self._exercise_permissions:
            self._exercise_permissions[user_id] = (self.exercise_ids(user_id), self.permits(user_id, 'exercise_library'))
        return self._exercise_permissions[user_id]

    def require_exercise(self, user, exercise) -> None:
        from app.core.exceptions import AppError
        from app.core.permissions import ADMIN_ROLES
        if not user:
            raise AppError(401, 'MEMBER_ACCESS_REQUIRED', 'Sign in to access your training')
        if user.role in ADMIN_ROLES or (user.role == 'COACH' and (exercise.owner_id == user.id or exercise.published)):
            return
        ids, library = self.exercise_policy(user.id)
        if exercise.id in ids or (exercise.published and library):
            return
        raise AppError(403, 'ENTITLEMENT_REQUIRED', 'This exercise is not included in your current access')
