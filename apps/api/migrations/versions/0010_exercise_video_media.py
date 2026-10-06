"""Link uploaded demonstration videos to exercises."""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("exercises") as batch:
        batch.add_column(sa.Column("video_media_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_exercises_video_media_id_media_assets", "media_assets", ["video_media_id"], ["id"])
        batch.create_index("ix_exercises_video_media_id", ["video_media_id"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("exercises") as batch:
        batch.drop_index("ix_exercises_video_media_id")
        batch.drop_constraint("fk_exercises_video_media_id_media_assets", type_="foreignkey")
        batch.drop_column("video_media_id")
