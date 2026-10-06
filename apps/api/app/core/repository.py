from typing import Any

from sqlalchemy import Select, func, inspect, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.logging import request_id_context
from app.modules.admin.models import AuditLog


def serialize(record: Any) -> dict[str, Any]:
    return {column.key: getattr(record, column.key) for column in inspect(type(record)).columns}


def require_record(db: Session, model: Any, record_id: str) -> Any:
    record = db.get(model, record_id)
    if record is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Record not found")
    return record


def paginate(db: Session, statement: Select, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    records = db.scalars(statement.limit(limit).offset(offset)).all()
    return {"items": [serialize(record) for record in records], "total": total}


def audit(db: Session, actor_id: str | None, action: str, resource: Any, details: dict[str, Any] | None = None) -> None:
    db.flush()
    db.add(AuditLog(request_id=request_id_context.get(), actor_id=actor_id, action=action,
                    resource_type=type(resource).__name__, resource_id=resource.id, details=details or {}))


def persist(db: Session, record: Any, actor_id: str | None, action: str) -> dict[str, Any]:
    db.add(record)
    audit(db, actor_id, action, record)
    db.commit()
    return serialize(record)
