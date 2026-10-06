"""Keep safe before/after details for security-sensitive account changes."""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("audit_logs") as batch:
        batch.add_column(sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))


def downgrade() -> None:
    with op.batch_alter_table("audit_logs") as batch:
        batch.drop_column("details")
