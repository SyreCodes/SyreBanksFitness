import smtplib
from email.message import EmailMessage
from typing import Protocol

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.jobs import celery_app


class EmailProvider(Protocol):
    def send(self, recipient: str, subject: str, body: str) -> None: ...


class SMTPEmailProvider:
    def send(self, recipient: str, subject: str, body: str) -> None:
        settings = get_settings()
        if not settings.smtp_host:
            raise AppError(503, "EMAIL_UNAVAILABLE", "Email delivery is not configured. Please contact the coach.")
        message = EmailMessage()
        message["To"] = recipient
        message["From"] = settings.email_from
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)


@celery_app.task(autoretry_for=(smtplib.SMTPException, OSError), retry_backoff=True, max_retries=4)
def send_email(recipient: str, subject: str, body: str) -> None:
    SMTPEmailProvider().send(recipient, subject, body)


@celery_app.task(autoretry_for=(smtplib.SMTPException, OSError), retry_backoff=True, max_retries=4)
def deliver_outbox(outbox_id: str) -> None:
    from app.core.database import SessionLocal
    from app.modules.auth.models import EmailOutbox
    with SessionLocal() as db:
        record = db.get(EmailOutbox, outbox_id)
        if not record or record.status == "SENT":
            return
        record.attempts += 1
        db.commit()
        SMTPEmailProvider().send(record.recipient, record.subject, record.body)
        record.status = "SENT"
        db.commit()


@celery_app.task
def dispatch_outbox() -> None:
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.modules.auth.models import EmailOutbox
    with SessionLocal() as db:
        ids = db.scalars(select(EmailOutbox.id).where(EmailOutbox.status == "PENDING", EmailOutbox.attempts < 5).limit(100)).all()
    for outbox_id in ids:
        deliver_outbox.delay(outbox_id)
