"""Update verification_logs with state machine fields.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-23 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add new columns
    op.add_column(
        "verification_logs",
        sa.Column(
            "state", sa.String(length=20), server_default="PENDING", nullable=False
        ),
    )
    op.add_column(
        "verification_logs",
        sa.Column("otp_hash", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "verification_logs",
        sa.Column("otp_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "verification_logs",
        sa.Column("otp_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "verification_logs",
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "verification_logs",
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
    )
    op.add_column(
        "verification_logs",
        sa.Column("channel", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "verification_logs",
        sa.Column("contact_info", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "verification_logs",
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "verification_logs",
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "verification_logs",
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Drop old columns
    op.drop_column("verification_logs", "verification_type")
    op.drop_column("verification_logs", "status")
    op.drop_column("verification_logs", "metadata")

    # Create indexes
    op.create_index(
        "ix_verification_logs_transaction_id",
        "verification_logs",
        ["transaction_id"],
        unique=False,
    )
    op.create_index(
        "ix_verification_logs_user_id",
        "verification_logs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_verification_logs_state",
        "verification_logs",
        ["state"],
        unique=False,
    )
    op.create_index(
        "ix_verification_logs_created_at",
        "verification_logs",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_verification_logs_created_at", table_name="verification_logs")
    op.drop_index("ix_verification_logs_state", table_name="verification_logs")
    op.drop_index("ix_verification_logs_user_id", table_name="verification_logs")
    op.drop_index("ix_verification_logs_transaction_id", table_name="verification_logs")

    # Add back old columns
    op.add_column(
        "verification_logs",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "verification_logs",
        sa.Column("status", sa.String(length=50), nullable=False),
    )
    op.add_column(
        "verification_logs",
        sa.Column("verification_type", sa.String(length=50), nullable=False),
    )

    # Drop new columns
    op.drop_column("verification_logs", "expired_at")
    op.drop_column("verification_logs", "failed_at")
    op.drop_column("verification_logs", "verified_at")
    op.drop_column("verification_logs", "contact_info")
    op.drop_column("verification_logs", "channel")
    op.drop_column("verification_logs", "max_attempts")
    op.drop_column("verification_logs", "attempts")
    op.drop_column("verification_logs", "otp_expires_at")
    op.drop_column("verification_logs", "otp_sent_at")
    op.drop_column("verification_logs", "otp_hash")
    op.drop_column("verification_logs", "state")
