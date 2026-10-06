"""Track exercise video upload IDs for safe retries."""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("media_assets") as batch:
        batch.add_column(sa.Column("upload_id", sa.String(128), nullable=True))
        batch.add_column(sa.Column("upload_sha256", sa.String(64), nullable=True))
        batch.create_index("ix_media_assets_upload_id", ["upload_id"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("media_assets") as batch:
        batch.drop_index("ix_media_assets_upload_id")
        batch.drop_column("upload_sha256")
        batch.drop_column("upload_id")
