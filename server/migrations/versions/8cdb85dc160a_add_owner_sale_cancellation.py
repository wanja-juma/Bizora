"""Add owner sale cancellation

Revision ID: 8cdb85dc160a
Revises: 4ac41c5e02bc
Create Date: 2026-11-25 14:48:59.358393

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8cdb85dc160a'
down_revision = '4ac41c5e02bc'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("sales") as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(20),
                nullable=False,
                server_default="completed",
            )
        )
        batch_op.add_column(
            sa.Column(
                "cancellation_reason",
                sa.String(255),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "cancelled_at",
                sa.DateTime(),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "cancelled_by_id",
                sa.Integer(),
                nullable=True,
            )
        )
        batch_op.create_foreign_key(
            "fk_sales_cancelled_by",
            "users",
            ["cancelled_by_id"],
            ["id"],
        )
        batch_op.create_check_constraint(
            "valid_sale_status",
            "status IN ('completed', 'cancelled')",
        )

    with op.batch_alter_table("stock_movements") as batch_op:
        batch_op.drop_constraint(
            "valid_stock_movement_kind",
            type_="check",
        )
        batch_op.create_check_constraint(
            "valid_stock_movement_kind",
            "kind IN "
            "('receipt', 'adjustment', 'sale', 'sale_cancellation')",
        )


def downgrade():
    # Removing cancellation history would lose audit information.
    connection = op.get_bind()

    count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM sales "
            "WHERE status = 'cancelled'"
        )
    ).scalar_one()

    if count:
        raise RuntimeError(
            "Cannot downgrade while cancelled sales exist."
        )

    with op.batch_alter_table("stock_movements") as batch_op:
        batch_op.drop_constraint(
            "valid_stock_movement_kind",
            type_="check",
        )
        batch_op.create_check_constraint(
            "valid_stock_movement_kind",
            "kind IN ('receipt', 'adjustment', 'sale')",
        )

    with op.batch_alter_table("sales") as batch_op:
        batch_op.drop_constraint(
            "valid_sale_status",
            type_="check",
        )
        batch_op.drop_constraint(
            "fk_sales_cancelled_by",
            type_="foreignkey",
        )
        batch_op.drop_column("cancelled_by_id")
        batch_op.drop_column("cancelled_at")
        batch_op.drop_column("cancellation_reason")
        batch_op.drop_column("status")
