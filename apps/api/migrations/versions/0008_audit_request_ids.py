"""Correlate immutable business audit entries with safe HTTP request identifiers."""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("audit_logs") as batch:
        batch.add_column(sa.Column("request_id", sa.String(36), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("audit_logs") as batch:
        batch.drop_column("request_id")
