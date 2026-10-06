"""Client feedback forum and unique per-user votes.

Revision ID: 0007
Revises: 0006
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("feedback_posts",
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("coach_response", sa.Text(), nullable=False),
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("category IN ('idea', 'feature', 'bug', 'compliment', 'general')", name="ck_feedback_category"),
        sa.CheckConstraint("status IN ('SUBMITTED', 'REVIEWING', 'PLANNED', 'IN_PROGRESS', 'COMPLETED', 'DECLINED')", name="ck_feedback_status"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"))
    for field in ["owner_id", "category", "status"]:
        op.create_index(f"ix_feedback_posts_{field}", "feedback_posts", [field])
    op.create_table("feedback_votes",
        sa.Column("post_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["feedback_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "user_id", name="uq_feedback_vote_user"))
    for field in ["post_id", "user_id"]:
        op.create_index(f"ix_feedback_votes_{field}", "feedback_votes", [field])


def downgrade() -> None:
    op.drop_table("feedback_votes")
    op.drop_table("feedback_posts")
