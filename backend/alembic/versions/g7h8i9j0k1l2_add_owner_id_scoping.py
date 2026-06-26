"""Add owner_id to transactions and fraud_rules for per-account isolation.

Each platform user owns their transactions and rules. Existing rows are
backfilled: transactions.owner_id = user_id; rules assigned to first admin.

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-25 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "g7h8i9j0k1l2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("owner_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "fraud_rules",
        sa.Column("owner_id", sa.UUID(), nullable=True),
    )

    op.execute(
        sa.text("UPDATE transactions SET owner_id = user_id WHERE owner_id IS NULL")
    )
    op.execute(
        sa.text(
            """
            UPDATE fraud_rules
            SET owner_id = (
                SELECT id FROM users WHERE role = 'admin' ORDER BY created_at ASC LIMIT 1
            )
            WHERE owner_id IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE fraud_rules
            SET owner_id = (SELECT id FROM users ORDER BY created_at ASC LIMIT 1)
            WHERE owner_id IS NULL
            """
        )
    )

    op.alter_column("transactions", "owner_id", nullable=False)
    op.alter_column("fraud_rules", "owner_id", nullable=False)

    op.create_foreign_key(
        "fk_transactions_owner_id_users",
        "transactions",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_fraud_rules_owner_id_users",
        "fraud_rules",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_transactions_owner_id", "transactions", ["owner_id"])
    op.create_index("ix_fraud_rules_owner_id", "fraud_rules", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_fraud_rules_owner_id", table_name="fraud_rules")
    op.drop_index("ix_transactions_owner_id", table_name="transactions")
    op.drop_constraint(
        "fk_fraud_rules_owner_id_users", "fraud_rules", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_transactions_owner_id_users", "transactions", type_="foreignkey"
    )
    op.drop_column("fraud_rules", "owner_id")
    op.drop_column("transactions", "owner_id")
