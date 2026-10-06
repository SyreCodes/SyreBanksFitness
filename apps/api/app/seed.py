"""Explicit, idempotent development fixtures. Never use to populate production."""
import copy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.models import (
    AuditLog,
    Booking,
    Checkin,
    ClientProfile,
    Exercise,
    Habit,
    Lead,
    Measurement,
    Message,
    Notification,
    Product,
    Program,
    ProgramAssignment,
    RefreshSession,
    Setting,
    User,
    WorkoutSession,
)
from app.core.security import hash_password
from app.modules.cms.services import DEFAULT_CONTENT


def seed() -> None:
    settings = get_settings()
    if settings.production:
        raise SystemExit("Development seed is prohibited in production")
    if min(len(settings.seed_admin_password), len(settings.seed_client_password)) < 12:
        raise SystemExit("Set SEED_ADMIN_PASSWORD and SEED_CLIENT_PASSWORD to explicit passwords of at least 12 characters")
    with SessionLocal() as db:
        existing_admin = db.scalar(select(User).where(User.email == "admin@syrebanksfitness.local"))
        if existing_admin:
            if existing_admin.demo and existing_admin.role == "ADMIN":
                existing_admin.role = "SUPER_ADMIN"
                existing_admin.token_version += 1
                db.execute(update(RefreshSession).where(RefreshSession.user_id == existing_admin.id).values(revoked=True))
                db.add(AuditLog(actor_id=existing_admin.id, action="development.demo_admin_promoted", resource_type="User",
                                resource_id=existing_admin.id, details={"previous_role": "ADMIN", "new_role": "SUPER_ADMIN"}))
                db.commit()
                print("Existing demo administrator promoted to super administrator; other records were preserved.")
                return
            print("Development seed already exists; existing records were preserved.")
            return
        admin = User(name="Syre Banks · Demo administrator", email="admin@syrebanksfitness.local", role="SUPER_ADMIN", password_hash=hash_password(settings.seed_admin_password), email_verified=True, status="ACTIVE", demo=True)
        db.add(admin)
        db.flush()
        coach = User(name="Demo coach · Synthetic", email="coach@syrebanksfitness.local", role="COACH", password_hash=hash_password(settings.seed_admin_password), email_verified=True, status="ACTIVE", demo=True)
        db.add(coach)
        db.flush()
        people = [("Demo Member", "client@syrebanksfitness.local", "Strength", "ONBOARDING"), ("Aline · Synthetic", "aline.demo@example.com", "Muscle Building", "ACTIVE"), ("Eric · Synthetic", "eric.demo@example.com", "Fat Loss", "ACTIVE"), ("Diane · Synthetic", "diane.demo@example.com", "Body Recomposition", "ACTIVE"), ("Jean · Synthetic", "jean.demo@example.com", "Strength", "PAUSED"), ("Grace · Synthetic", "grace.demo@example.com", "Beginner Transformation", "ACTIVE")]
        clients = []
        for name, email, goal, status in people:
            client = User(name=name, email=email, role="CLIENT", password_hash=hash_password(settings.seed_client_password), assigned_coach_id=coach.id, goal=goal, status=status, demo=True)
            db.add(client)
            db.flush()
            db.add(ClientProfile(client_id=client.id, assessment={"primary_goal": goal, "training_experience": "beginner", "environment": "gym", "training_days": ["Monday", "Wednesday", "Friday"]}, health_screening={}, notes="Synthetic development client record."))
            clients.append(client)
        exercises = []
        for name, group, equipment, instructions, cues in [
            ("Goblet Squat", "Legs", "Dumbbell", "Hold a dumbbell at chest height. Brace, sit between your hips and stand with control.", ["Keep your whole foot planted", "Choose a comfortable depth"]),
            ("Dumbbell Bench Press", "Chest", "Dumbbells", "Lie on a flat bench. Lower the dumbbells with control and press back up.", ["Keep wrists stacked", "Avoid bouncing"]),
            ("Romanian Deadlift", "Posterior chain", "Barbell", "Hinge at the hips with a neutral spine. Keep the load close and return to standing.", ["Soft knees", "Stop before your back rounds"]),
            ("Lat Pulldown", "Back", "Cable machine", "Pull the handle toward your upper chest and control the return.", ["Avoid swinging", "Lead with your elbows"]),
            ("Plank", "Core", "Bodyweight", "Support your body on forearms and toes. Brace while breathing steadily.", ["Keep hips level", "Use short quality holds"]),
            ("Reverse Lunge", "Legs", "Bodyweight", "Step back into a controlled lunge and return through your front foot.", ["Keep balance", "Reduce range if uncomfortable"]),
            ("Seated Cable Row", "Back", "Cable machine", "Sit tall, pull the handle toward your torso, then return under control.", ["Keep shoulders relaxed", "Avoid using momentum"]),
            ("Dumbbell Shoulder Press", "Shoulders", "Dumbbells", "Press from shoulder height in a comfortable range and lower under control.", ["Brace your trunk", "Avoid arching excessively"]),
        ]:
            exercise = Exercise(name=name, muscle_group=group, equipment=equipment, difficulty="Beginner", description=f"A foundational {group.lower()} movement.", instructions=instructions, coach_cues=cues, owner_id=admin.id, published=True, demo=True)
            db.add(exercise)
            db.flush()
            exercises.append(exercise)
        workouts = []
        for day, name, indices in [(1, "Full Body A", [0, 1, 3, 4]), (3, "Full Body B", [2, 6, 7, 4]), (5, "Full Body C", [5, 1, 6, 4])]:
            workouts.append({"id": str(uuid4()), "name": name, "day": day, "exercises": [{"exercise_id": exercises[index].id, "name": exercises[index].name, "sets": 3, "reps": "8–12", "rest_seconds": 90} for index in indices]})
        program = Program(name="Foundations of Strength", description="An eight-week full-body coaching template. Your coach adapts exercise selection and loading to your assessment.", goal="Strength", difficulty="Beginner", weeks=8, workouts=workouts, owner_id=admin.id, published=True, demo=True)
        db.add(program)
        db.flush()
        for client in clients:
            assignment = ProgramAssignment(client_id=client.id, program_id=program.id, assigned_by=admin.id, snapshot={"id": program.id, "name": program.name, "description": program.description, "goal": program.goal, "difficulty": program.difficulty, "weeks": 8, "workouts": copy.deepcopy(workouts)}, status="ACTIVE")
            db.add(assignment)
            db.flush()
            for habit in ["Move for 20 minutes", "Plan tomorrow's meals"]:
                db.add(Habit(client_id=client.id, name=habit, description="Synthetic example; adapt with your coach.", frequency="daily"))
            if client.status == "ACTIVE":
                db.add(WorkoutSession(client_id=client.id, assignment_id=assignment.id, workout_id=workouts[0]["id"], sets=[{"exercise_id": exercises[0].id, "set_number": 1, "reps": 10, "weight_kg": 12, "rpe": 6, "completed": True}], duration_minutes=40, completed=True, notes="Synthetic development workout."))
            for delta, weight in [(21, 76.0), (14, 75.8), (7, 75.6), (0, 75.5)]:
                db.add(Measurement(client_id=client.id, kind="weight", value=weight, unit="kg", recorded_at=(datetime.now(UTC) - timedelta(days=delta)).isoformat()))
        for client in clients[:3]:
            db.add(Checkin(client_id=client.id, answers={"energy": 4, "sleep": 3, "adherence": 4, "wins": "Synthetic example: completed the planned sessions.", "challenges": "Synthetic example: busy work schedule."}, template_snapshot={"version": "2026-01"}, notes="Synthetic check-in awaiting coach review."))
        client = clients[0]
        db.add(Message(sender_id=coach.id, recipient_id=client.id, body="Welcome to the demo workspace. Complete your assessment, review your assigned program and message your coach with questions."))
        db.add(Notification(user_id=client.id, title="Welcome to your demo coaching workspace", body="All records in this seeded account are synthetic.", link="/app/onboarding"))
        db.add(Notification(user_id=admin.id, title="Development workspace ready", body="Demo records are synthetic. Financial revenue remains zero until verified payments.", link="/admin"))
        for name, email, goal, stage in [("Chris · Synthetic", "chris.lead@example.com", "Muscle Building", "NEW"), ("Patricia · Synthetic", "patricia.lead@example.com", "Fat Loss", "QUALIFIED"), ("Alex · Synthetic", "alex.lead@example.com", "Beginner Transformation", "CONSULTATION_BOOKED")]:
            db.add(Lead(name=name, email=email, goal=goal, stage=stage, source="DEMO", consent_version="synthetic-demo", responses={"demo": True, "training_experience": "beginner", "coaching_preference": "remote"}, notes="Synthetic development application.", assigned_coach_id=coach.id, demo=True))
        entitlements = {"program_access": True, "coach_messaging": True, "weekly_checkin": True, "form_review": True, "nutrition_guidance": True, "live_sessions_per_month": 0, "exercise_library": True}
        features = ["Personalized training program", "Weekly coach check-ins", "Coach messaging", "Progress and habit tracking", "Nutrition guidance"]
        db.add(Product(name="Online Coaching · Monthly", description="Personal coaching, consistent accountability and a training plan built around you.", price_minor=10000, currency="USD", billing_interval="monthly", features=features, entitlements=entitlements, demo=True))
        db.add(Product(name="Online Coaching · Annual", description="Twelve months of structured coaching. Annual billing at $1,200.", price_minor=120000, currency="USD", billing_interval="annual", features=features, entitlements=entitlements, demo=True))
        db.add(Setting(key="business", value=copy.deepcopy(DEFAULT_CONTENT)))
        tomorrow = datetime.now(UTC) + timedelta(days=1)
        while tomorrow.weekday() not in [0, 1, 2, 3, 4]:
            tomorrow += timedelta(days=1)
        starts = tomorrow.replace(hour=7, minute=0, second=0, microsecond=0)
        db.add(Booking(client_id=client.id, coach_id=coach.id, starts_at=starts, ends_at=starts + timedelta(hours=1), type="live_training", notes="Synthetic demonstration session."))
        db.add(AuditLog(actor_id=admin.id, action="development.seeded", resource_type="DevelopmentWorkspace"))
        db.commit()
        print("Synthetic development workspace seeded. No payments, invoices or client consents were fabricated.")


if __name__ == "__main__":
    seed()
