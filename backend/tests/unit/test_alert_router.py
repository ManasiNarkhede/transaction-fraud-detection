"""Unit tests for alert router."""

from __future__ import annotations

from app.services.alert_router import AlertRouter


class TestAlertRouter:
    """Tests for AlertRouter."""

    def test_route_alert_block_high_score(self) -> None:
        channels = AlertRouter.route_alert("block", 95)
        assert channels == ["email", "sms"]

    def test_route_alert_block_medium_score(self) -> None:
        channels = AlertRouter.route_alert("block", 85)
        assert channels == ["email"]

    def test_route_alert_verify(self) -> None:
        channels = AlertRouter.route_alert("verify", 60)
        assert channels == ["email"]

    def test_route_alert_approve(self) -> None:
        channels = AlertRouter.route_alert("approve", 30)
        assert channels == []

    def test_route_alert_unknown_decision(self) -> None:
        channels = AlertRouter.route_alert("unknown", 50)
        assert channels == []

    def test_route_alert_block_boundary_90(self) -> None:
        channels = AlertRouter.route_alert("block", 90)
        assert channels == ["email"]

    def test_route_alert_block_boundary_91(self) -> None:
        channels = AlertRouter.route_alert("block", 91)
        assert channels == ["email", "sms"]

    def test_get_priority_critical(self) -> None:
        priority = AlertRouter.get_priority("block", 95)
        assert priority == "critical"

    def test_get_priority_high(self) -> None:
        priority = AlertRouter.get_priority("block", 85)
        assert priority == "high"

    def test_get_priority_medium(self) -> None:
        priority = AlertRouter.get_priority("verify", 60)
        assert priority == "medium"

    def test_get_priority_low(self) -> None:
        priority = AlertRouter.get_priority("approve", 30)
        assert priority == "low"

    def test_get_priority_unknown(self) -> None:
        priority = AlertRouter.get_priority("unknown", 50)
        assert priority == "low"
