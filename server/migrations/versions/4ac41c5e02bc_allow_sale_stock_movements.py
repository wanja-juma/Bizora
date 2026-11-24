"""Allow sale stock movements

Revision ID: 4ac41c5e02bc
Revises: 018c9aaaa095
Create Date: 2026-11-24 23:47:52.157910

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4ac41c5e02bc'
down_revision = '018c9aaaa095'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("stock_movements") as batch_op:
        batch_op.drop_constraint(
            "valid_stock_movement_kind",
            type_="check",
        )
        batch_op.create_check_constraint(
            "valid_stock_movement_kind",
            "kind IN ('receipt', 'adjustment', 'sale')",
        )


def downgrade():
    with op.batch_alter_table("stock_movements") as batch_op:
        batch_op.drop_constraint(
            "valid_stock_movement_kind",
            type_="check",
        )
        batch_op.create_check_constraint(
            "valid_stock_movement_kind",
            "kind IN ('receipt', 'adjustment')",
        )



