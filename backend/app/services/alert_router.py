"""Severity-based alert routing."""

from __future__ import annotations


class AlertRouter:
    """Routes fraud alerts to user contact channels based on severity."""

    @staticmethod
    def route_alert(decision: str, score: int) -> list[str]:
        """Determine which channels to use for an alert.

        Alerts go to the account owner's registration email (and phone for
        critical blocks). Returns channel names: ``email``, ``sms``.
        """
        if decision == "block":
            if score > 90:
                return ["email", "sms"]
            return ["email"]
        if decision == "verify":
            return ["email"]
        return []

    @staticmethod
    def get_priority(decision: str, score: int) -> str:
        """Get alert priority level."""
        if decision == "block" and score > 90:
            return "critical"
        if decision == "block":
            return "high"
        if decision == "verify":
            return "medium"
        return "low"
