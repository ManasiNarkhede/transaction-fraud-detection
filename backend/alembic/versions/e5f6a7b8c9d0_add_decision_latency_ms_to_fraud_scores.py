"""Add decision_latency_ms to fraud_scores.

Tracks per-transaction decision latency (milliseconds) so the dashboard
can report avg/p95 latency KPI. Column is nullable so existing rows are
unaffected.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-25 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "fraud_scores",
        sa.Column("decision_latency_ms", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("fraud_scores", "decision_latency_ms")
