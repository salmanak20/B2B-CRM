"""Retain storage quota until ambiguous upload cleanup is confirmed."""
from alembic import op
import sqlalchemy as sa
revision='a1b2c3d4e509'
down_revision='a1b2c3d4e508'
branch_labels=depends_on=None


def upgrade():
    op.add_column('attachments',sa.Column('upload_state',sa.String(10),nullable=False,server_default='ready'))
    op.create_check_constraint('ck_attachment_upload_state','attachments',"upload_state IN ('pending','ready')")


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM attachments WHERE upload_state='pending')")):
        raise RuntimeError('Refusing to discard pending upload reservations')
    op.drop_constraint('ck_attachment_upload_state','attachments',type_='check')
    op.drop_column('attachments','upload_state')
