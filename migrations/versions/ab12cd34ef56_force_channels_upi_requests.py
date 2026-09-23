"""force_channels + upi_requests tables

Revision ID: ab12cd34ef56
Revises: d7e8f9a0b1c2
Create Date: 2026-09-23 20:00:00.000000

"""

# =============================================================================
#  Copyright (c) 2026 Saksham Swaroop (@truenakshu)  |  GitHub: VIP-saksham
#  LinkedIn: sakshamswaroop
#
#  All rights reserved. This source code is the private property of the
#  author. Copying, modifying, redistributing or deploying any part of this
#  file WITHOUT the author's written permission is strictly prohibited.
#  For licensing / permission: https://t.me/truenakshu
# =============================================================================
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ab12cd34ef56'
down_revision: Union[str, None] = 'd7e8f9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'force_channels',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('chat_id', sa.String(64), nullable=False, unique=True),
        sa.Column('username', sa.String(64), nullable=True),
        sa.Column('title', sa.String(128), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        'upi_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.telegram_id', ondelete='CASCADE'), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('utr', sa.String(64), nullable=True),
        sa.Column('status', sa.String(24), nullable=False, server_default='pending'),
        sa.Column('verify_message_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_upi_requests_user_id', 'upi_requests', ['user_id'])
    op.create_index('ix_upi_requests_status_created', 'upi_requests', ['status', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_upi_requests_status_created', table_name='upi_requests')
    op.drop_index('ix_upi_requests_user_id', table_name='upi_requests')
    op.drop_table('upi_requests')
    op.drop_table('force_channels')
