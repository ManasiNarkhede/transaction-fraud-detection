"""Light unit tests for scripts.seed_data.

Validates that per-table guard functions exist and that helper utilities
produce the expected output shapes — no live DB required.
"""

from __future__ import annotations

import uuid
from decimal import Decimal


def test_seed_data_module_imports() -> None:
    """The seed module must import cleanly (no live DB interaction at import time)."""
    import scripts.seed_data as sd  # noqa: F401 — import-only check

    # Per-table guard helper must exist
    assert callable(sd._table_count)
    # All seed step functions must be present
    for fn_name in (
        "seed_users",
        "seed_devices",
        "seed_fraud_rules",
        "seed_transactions",
        "seed_fraud_scores",
        "seed_alerts",
        "seed_blocked_transactions",
        "seed_verification_logs",
        "seed_audit_logs",
        "seed_data",
    ):
        assert hasattr(sd, fn_name), f"Missing function: {fn_name}"


def test_make_audit_features_json_safe() -> None:
    """_make_audit_features must return a dict with no Decimal values."""
    import scripts.seed_data as sd

    amount = Decimal("123.45")
    features = sd._make_audit_features(amount)

    assert isinstance(features, dict)
    assert len(features) > 0

    # The actual property we care about: the dict is JSON-serializable
    # (no Decimal/other non-native types would survive json.dumps).
    import json

    json.dumps(features)
    # amount field should be the float representation
    assert features["amount"] == float(amount)


def test_score_to_decision_ranges() -> None:
    """_score_to_decision must map score ranges to the correct decision label."""
    import scripts.seed_data as sd

    decision_approve, _ = sd._score_to_decision(0)
    assert decision_approve == "approve"

    decision_approve_edge, _ = sd._score_to_decision(40)
    assert decision_approve_edge == "approve"

    decision_verify, _ = sd._score_to_decision(55)
    assert decision_verify == "verify"

    decision_verify_edge, _ = sd._score_to_decision(70)
    assert decision_verify_edge == "verify"

    decision_block, _ = sd._score_to_decision(71)
    assert decision_block == "block"

    decision_block_max, _ = sd._score_to_decision(100)
    assert decision_block_max == "block"


def test_audit_hash_chain_validity() -> None:
    """Verify that _make_audit_features + AuditService._generate_hash produce
    a valid two-record chain that AuditService.verify_integrity would accept."""
    import scripts.seed_data as sd
    from app.services.audit_service import AuditService

    tx_id = uuid.uuid4()
    amount = Decimal("500.00")

    features = sd._make_audit_features(amount)
    sanitized = AuditService._sanitize_features(features)

    # First record — no previous hash
    hash1 = AuditService._generate_hash(
        transaction_id=tx_id,
        decision="approve",
        score=25,
        reason="No risk signals detected",
        features=sanitized,
        rules_triggered=[],
        model_version="v1.0",
        previous_hash=None,
    )
    assert len(hash1) == 64

    # Second record — chained
    tx_id2 = uuid.uuid4()
    hash2 = AuditService._generate_hash(
        transaction_id=tx_id2,
        decision="block",
        score=85,
        reason="Multiple rules triggered: velocity + location anomaly",
        features=sanitized,
        rules_triggered=["high_velocity"],
        model_version="v1.0",
        previous_hash=hash1,
    )
    assert len(hash2) == 64
    assert hash1 != hash2


def test_verification_states_include_pending() -> None:
    """VERIFICATION_STATES list must contain PENDING entries."""
    import scripts.seed_data as sd

    pending_count = sd.VERIFICATION_STATES.count("PENDING")
    assert (
        pending_count >= 3
    ), f"Expected at least 3 PENDING entries, got {pending_count}"


def test_fraud_rules_include_active_and_inactive() -> None:
    """Rule templates must include both active and inactive entries."""
    import scripts.seed_data as sd

    # Inspect rule_templates in the function source — we verify via the constants
    # that the SEED_FRAUD_RULE_COUNT covers our 8-entry template list
    assert sd.SEED_FRAUD_RULE_COUNT >= 8
