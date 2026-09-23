"""captcha_passed flag on users

Revision ID: f6a7b8c9d0e1
Revises: ab12cd34ef56
Create Date: 2026-09-23 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'ab12cd34ef56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('users')]
    if 'captcha_passed' not in columns:
        op.add_column('users', sa.Column('captcha_passed', sa.Boolean(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('users')]
    if 'captcha_passed' in columns:
        op.drop_column('users', 'captcha_passed')
