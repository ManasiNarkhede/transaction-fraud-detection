"""Datetime helpers aligned with Postgres TIMESTAMP WITHOUT TIME ZONE columns."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now_naive() -> datetime:
    """Return the current UTC time as a naive datetime for DB writes."""
    return datetime.now(UTC).replace(tzinfo=None)
