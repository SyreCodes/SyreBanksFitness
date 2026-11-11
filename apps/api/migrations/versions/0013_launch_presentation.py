"""Add launch metadata and authenticated enrollment ownership; preserve legacy writes."""
import sqlalchemy as sa
from alembic import op

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('programs', 'products'):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column('launch_details', sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    with op.batch_alter_table('leads') as batch:
        batch.add_column(sa.Column('user_id', sa.String(36), nullable=True))
        batch.create_foreign_key('fk_leads_user_id', 'users', ['user_id'], ['id'])
        batch.create_index('ix_leads_user_id', ['user_id'])


def downgrade():
    with op.batch_alter_table('leads') as batch:
        batch.drop_index('ix_leads_user_id')
        batch.drop_constraint('fk_leads_user_id', type_='foreignkey')
        batch.drop_column('user_id')
    for table in ('products', 'programs'):
        with op.batch_alter_table(table) as batch:
            batch.drop_column('launch_details')
