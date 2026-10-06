"""Private movement video submissions and coach feedback.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "form_checks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("exercise_id", sa.String(36), sa.ForeignKey("exercises.id"), nullable=False),
        sa.Column("exercise_name", sa.String(120), nullable=False),
        sa.Column("media_asset_id", sa.String(36), sa.ForeignKey("media_assets.id"), nullable=False, unique=True),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("timestamped_notes", sa.JSON(), nullable=False),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
    )
    for column in ["client_id", "exercise_id", "status"]:
        op.create_index(f"ix_form_checks_{column}", "form_checks", [column])


def downgrade() -> None:
    op.drop_table("form_checks")
