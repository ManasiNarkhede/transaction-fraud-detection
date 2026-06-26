"""Development seed data script.

Idempotent seeding for local development. Safe to run multiple times.
Each seed step only runs if its table is empty (or below target count),
so re-running fills whatever is missing without duplicating rows.

Usage:
    python -m scripts.seed_data
"""

from __future__ import annotations

import asyncio
import random
import uuid
from decimal import Decimal

from faker import Faker
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.models import (
    Alert,
    BlockedTransaction,
    Device,
    FraudDecisionAudit,
    FraudRule,
    FraudScore,
    Transaction,
    User,
    VerificationLog,
)
from app.services.audit_service import AuditService

fake = Faker()

# Create a local async session maker for the seed script
async_engine = create_async_engine(settings.database_url)
async_session_maker = async_sessionmaker(async_engine, expire_on_commit=False)

# Pre-defined seed passwords (hashed with a dummy hash for dev only)
# In a real app these would be bcrypt hashes; here we use a placeholder.
DUMMY_HASHED_PASSWORD = (
    "$2b$12$dummyhashplaceholderfordevelopmentonlynotforproductionuse"
)

# Seed configuration
SEED_USER_COUNT = 10
SEED_TRANSACTION_COUNT = 50
SEED_FRAUD_RULE_COUNT = 8

USER_ROLES = ["analyst", "admin"]
TRANSACTION_STATUSES = ["pending", "approved", "blocked", "flagged"]
ALERT_TYPES = ["velocity", "amount", "location", "device", "merchant"]
ALERT_SEVERITIES = ["low", "medium", "high", "critical"]
ALERT_STATUSES = ["open", "investigating", "resolved", "dismissed"]
# Ensure several PENDING so the Verifications default queue shows items
VERIFICATION_STATES = [
    "PENDING",
    "PENDING",
    "PENDING",
    "VERIFIED",
    "VERIFIED",
    "FAILED",
    "EXPIRED",
]
VERIFICATION_CHANNELS = ["sms", "email"]
BLOCK_REASONS = [
    "Velocity limit exceeded",
    "Unusual location",
    "High-risk merchant",
    "Suspicious device fingerprint",
    "Amount exceeds threshold",
]
FRAUD_RULE_TYPES = ["velocity", "amount", "location", "device", "time"]
FRAUD_RULE_ACTIONS = ["block", "flag", "review", "alert"]

# Audit decisions correlated to score ranges
_APPROVE_REASONS = [
    "No risk signals detected",
    "Transaction within normal parameters",
    "Low velocity, trusted device",
    "Amount matches historical average",
]
_VERIFY_REASONS = [
    "Moderate velocity spike; OTP verification requested",
    "Slightly elevated amount; additional verification required",
    "New device detected; 2FA sent",
    "Unusual merchant category; verification triggered",
]
_BLOCK_REASONS_AUDIT = [
    "Multiple rules triggered: velocity + location anomaly",
    "Score exceeds block threshold; high-risk merchant",
    "Suspected card-not-present fraud pattern",
    "Geo-velocity impossibility detected",
]


async def _table_count(session, model) -> int:  # type: ignore[no-untyped-def]
    """Return the row count for *model*'s table."""
    result = await session.execute(select(func.count()).select_from(model))
    return result.scalar_one() or 0


async def get_or_create(  # type: ignore[no-untyped-def]
    session,
    model,
    defaults=None,
    **kwargs,
):
    """Get an existing record or create a new one.

    Returns:
        Tuple of (instance, created) where created is a bool.
    """
    result = await session.execute(select(model).filter_by(**kwargs))
    instance = result.scalar_one_or_none()
    if instance:
        return instance, False
    params = {**kwargs, **(defaults or {})}
    instance = model(**params)
    session.add(instance)
    await session.flush()
    return instance, True


async def seed_users(session, count: int = SEED_USER_COUNT) -> list[User]:  # type: ignore[no-untyped-def]
    """Seed users with various roles (get_or_create idempotent)."""
    users: list[User] = []
    for i in range(count):
        role = "admin" if i == 0 else random.choice(USER_ROLES)
        email = f"user{i + 1}@example.com"
        user, created = await get_or_create(
            session,
            User,
            defaults={
                "email": email,
                "hashed_password": DUMMY_HASHED_PASSWORD,
                "full_name": fake.name(),
                "role": role,
                "is_active": True,
            },
            email=email,
        )
        users.append(user)
    new_count = sum(1 for _ in users)
    print(f"Users: {new_count} present (get_or_create)")
    return users


async def seed_devices(session, users: list[User]) -> list[Device]:  # type: ignore[no-untyped-def]
    """Seed devices — skip if Device table already has rows."""
    if await _table_count(session, Device) > 0:
        print("Devices already seeded, skipping.")
        return []
    devices: list[Device] = []
    for user in users:
        for _ in range(random.randint(1, 3)):
            fingerprint = fake.uuid4()
            device = Device(
                user_id=user.id,
                device_fingerprint=fingerprint,
                device_type=random.choice(["mobile", "desktop", "tablet"]),
                last_seen=fake.date_time_between(start_date="-30d", end_date="now"),
                trust_score=Decimal(str(round(random.uniform(0.1, 0.99), 2))),
            )
            session.add(device)
            devices.append(device)
    await session.flush()
    print(f"Created {len(devices)} devices")
    return devices


async def seed_fraud_rules(
    session: AsyncSession, count: int = SEED_FRAUD_RULE_COUNT
) -> list[FraudRule]:
    """Seed fraud detection rules — skip if FraudRule table already has rows."""
    if await _table_count(session, FraudRule) > 0:
        print("Fraud rules already seeded, skipping.")
        result = await session.execute(select(FraudRule))
        return list(result.scalars().all())
    rules: list[FraudRule] = []
    rule_templates = [
        ("High Velocity Block", "velocity", "block", True),
        ("Large Amount Alert", "amount", "alert", True),
        ("New Device Review", "device", "review", True),
        ("Geo-Anomaly Flag", "location", "flag", True),
        ("Off-Hours Check", "time", "review", True),
        ("Repeated Failures Block", "velocity", "block", True),
        ("Cross-Border Alert", "location", "alert", False),
        ("Daily Limit Check", "amount", "flag", False),
    ]
    for i in range(min(count, len(rule_templates))):
        name, rtype, action, is_active = rule_templates[i]
        rule = FraudRule(
            name=name,
            description=fake.sentence(),
            rule_type=rtype,
            conditions={
                "threshold": random.randint(100, 10000),
                "window_minutes": random.choice([5, 15, 30, 60]),
            },
            action=action,
            priority=random.randint(1, 500),
            is_active=is_active,
            score_value=random.randint(10, 50),
        )
        session.add(rule)
        rules.append(rule)
    await session.flush()
    print(f"Created {len(rules)} fraud rules")
    return rules


async def seed_transactions(  # type: ignore[no-untyped-def]
    session, users: list[User], count: int = SEED_TRANSACTION_COUNT
) -> list[Transaction]:
    """Seed transactions — skip if Transaction table already has rows."""
    existing_count = await _table_count(session, Transaction)
    if existing_count > 0:
        print(
            f"Transactions already present ({existing_count} rows), fetching existing."
        )
        result = await session.execute(select(Transaction).limit(count))
        return list(result.scalars().all())
    transactions: list[Transaction] = []
    for _ in range(count):
        user = random.choice(users)
        tx = Transaction(
            id=uuid.uuid4(),
            user_id=user.id,
            amount=Decimal(str(round(random.uniform(1.0, 5000.0), 2))),
            currency=random.choice(["USD", "EUR", "GBP", "CAD"]),
            merchant_id=fake.uuid4(),
            merchant_category=random.choice(
                [
                    "grocery",
                    "electronics",
                    "travel",
                    "dining",
                    "retail",
                    "entertainment",
                ]
            ),
            card_last_four=fake.numerify("####"),
            ip_address=fake.ipv4(),
            device_fingerprint=fake.uuid4(),
            status=random.choice(TRANSACTION_STATUSES),
        )
        session.add(tx)
        transactions.append(tx)
    await session.flush()
    print(f"Created {len(transactions)} transactions")
    return transactions


async def seed_fraud_scores(  # type: ignore[no-untyped-def]
    session, transactions: list[Transaction], users: list[User]
) -> list[FraudScore]:
    """Seed fraud scores — skip if FraudScore table already has rows."""
    if await _table_count(session, FraudScore) > 0:
        print("Fraud scores already seeded, skipping.")
        return []
    fraud_scores: list[FraudScore] = []
    scored_transactions = random.sample(transactions, k=int(len(transactions) * 0.6))
    for tx in scored_transactions:
        score_value = Decimal(str(round(random.uniform(0.0, 1.0), 4)))
        fs = FraudScore(
            transaction_id=tx.id,
            user_id=tx.user_id,
            model_version=f"v{random.randint(1, 5)}.{random.randint(0, 9)}",
            score=score_value,
            features_used={
                "amount_factor": round(random.uniform(0, 1), 4),
                "velocity_factor": round(random.uniform(0, 1), 4),
                "device_trust": round(random.uniform(0, 1), 4),
                "location_risk": round(random.uniform(0, 1), 4),
            },
        )
        session.add(fs)
        fraud_scores.append(fs)
    await session.flush()
    print(f"Created {len(fraud_scores)} fraud scores")
    return fraud_scores


async def seed_alerts(  # type: ignore[no-untyped-def]
    session, transactions: list[Transaction], users: list[User]
) -> list[Alert]:
    """Seed alerts — skip if Alert table already has rows."""
    if await _table_count(session, Alert) > 0:
        print("Alerts already seeded, skipping.")
        return []
    alerts: list[Alert] = []
    alert_candidates = [
        tx
        for tx in transactions
        if tx.amount > Decimal("1000") or random.random() > 0.7
    ]
    for tx in alert_candidates:
        assigned_to = random.choice(users).id if random.random() > 0.3 else None
        # Mix: ensure some "open" alerts so the Alerts page has targets to act on
        status = random.choice(ALERT_STATUSES)
        resolved_at = (
            fake.date_time_between(start_date="-7d", end_date="now")
            if status in ("resolved", "dismissed")
            else None
        )
        alert = Alert(
            transaction_id=tx.id,
            user_id=tx.user_id,
            alert_type=random.choice(ALERT_TYPES),
            severity=random.choice(ALERT_SEVERITIES),
            status=status,
            assigned_to=assigned_to,
            resolved_at=resolved_at,
        )
        session.add(alert)
        alerts.append(alert)
    await session.flush()
    print(f"Created {len(alerts)} alerts")
    return alerts


async def seed_blocked_transactions(  # type: ignore[no-untyped-def]
    session, transactions: list[Transaction], users: list[User]
) -> list[BlockedTransaction]:
    """Seed blocked transactions — skip if BlockedTransaction table already has rows."""
    if await _table_count(session, BlockedTransaction) > 0:
        print("Blocked transactions already seeded, skipping.")
        return []
    blocked: list[BlockedTransaction] = []
    blocked_txs = [tx for tx in transactions if tx.status == "blocked"]
    for tx in blocked_txs:
        reviewed_by = random.choice(users).id if random.random() > 0.4 else None
        reviewed_at = (
            fake.date_time_between(start_date="-7d", end_date="now")
            if reviewed_by
            else None
        )
        bt = BlockedTransaction(
            transaction_id=tx.id,
            user_id=tx.user_id,
            reason=random.choice(BLOCK_REASONS),
            rule_triggered=f"rule_{random.randint(1, 5)}",
            blocked_at=fake.date_time_between(start_date="-30d", end_date="now"),
            reviewed_by=reviewed_by,
            reviewed_at=reviewed_at,
            review_decision=(
                random.choice(["confirmed_fraud", "false_positive", None])
                if reviewed_by
                else None
            ),
        )
        session.add(bt)
        blocked.append(bt)
    await session.flush()
    print(f"Created {len(blocked)} blocked transaction records")
    return blocked


async def seed_verification_logs(  # type: ignore[no-untyped-def]
    session, transactions: list[Transaction], users: list[User]
) -> list[VerificationLog]:
    """Seed verification logs — skip if VerificationLog table already has rows.

    Ensures several PENDING entries so the default Verifications queue shows items.
    """
    if await _table_count(session, VerificationLog) > 0:
        print("Verification logs already seeded, skipping.")
        return []
    logs: list[VerificationLog] = []
    # Use ~40% of transactions so there's a good spread
    sample_size = max(15, int(len(transactions) * 0.4))
    log_candidates = random.sample(transactions, k=min(sample_size, len(transactions)))
    for tx in log_candidates:
        # Weighted list: 3 PENDING entries for every 4 non-PENDING
        state = random.choice(VERIFICATION_STATES)
        channel = random.choice(VERIFICATION_CHANNELS)
        contact_info = (
            fake.email() if channel == "email" else fake.numerify("+1##########")
        )
        otp_sent_at = fake.date_time_between(start_date="-7d", end_date="now")
        otp_expires_at = fake.date_time_between(start_date="-6d", end_date="now")
        vl = VerificationLog(
            transaction_id=tx.id,
            user_id=tx.user_id,
            state=state,
            channel=channel,
            contact_info=contact_info,
            attempts=random.randint(0, 3),
            max_attempts=3,
            otp_sent_at=otp_sent_at,
            otp_expires_at=otp_expires_at,
            verified_at=otp_sent_at if state == "VERIFIED" else None,
            failed_at=otp_sent_at if state == "FAILED" else None,
            expired_at=otp_sent_at if state == "EXPIRED" else None,
        )
        session.add(vl)
        logs.append(vl)
    await session.flush()
    pending_count = sum(1 for vl in logs if vl.state == "PENDING")
    print(f"Created {len(logs)} verification logs ({pending_count} PENDING)")
    return logs


def _make_audit_features(amount: Decimal) -> dict[str, float | int | bool]:
    """Build a JSON-safe features dict (no Decimal) for an audit record."""
    return {
        "amount": float(amount),
        "amount_zscore": round(random.uniform(-2.0, 4.0), 4),
        "velocity_1h": random.randint(0, 10),
        "velocity_24h": random.randint(0, 25),
        "device_trust_score": round(random.uniform(0.1, 1.0), 4),
        "is_new_device": random.choice([True, False]),
        "hour_of_day": random.randint(0, 23),
        "is_weekend": random.choice([True, False]),
        "unique_merchants_24h": random.randint(1, 8),
    }


def _score_to_decision(score: int) -> tuple[str, str]:
    """Return (decision, reason) for a given integer score 0-100."""
    if score <= 40:
        return "approve", random.choice(_APPROVE_REASONS)
    elif score <= 70:
        return "verify", random.choice(_VERIFY_REASONS)
    else:
        return "block", random.choice(_BLOCK_REASONS_AUDIT)


async def seed_audit_logs(  # type: ignore[no-untyped-def]
    session, transactions: list[Transaction]
) -> list[FraudDecisionAudit]:
    """Seed fraud_decision_audits with a valid hash chain.

    Skipped if FraudDecisionAudit table already has rows.
    Uses AuditService._generate_hash and _sanitize_features to match the
    exact hashing the live engine uses, so Verify Integrity passes.
    """
    if await _table_count(session, FraudDecisionAudit) > 0:
        print("Audit logs already seeded, skipping.")
        return []

    audit_records: list[FraudDecisionAudit] = []
    previous_hash: str | None = None

    # Use all transactions so the Transactions page and Audit Log are both populated
    for tx in transactions:
        score = random.randint(0, 100)
        decision, reason = _score_to_decision(score)
        raw_features = _make_audit_features(tx.amount)
        # Sanitize (removes PII keys — our dict has none, but mirrors live flow)
        features = AuditService._sanitize_features(raw_features)
        rules_triggered: list[str] = []
        if score > 40:
            rules_triggered.append(
                random.choice(["high_velocity", "geo_anomaly", "large_amount"])
            )
        if score > 70:
            rules_triggered.append(random.choice(["new_device", "repeated_failure"]))
        model_version = f"v{random.randint(1, 3)}.{random.randint(0, 5)}"

        record_hash = AuditService._generate_hash(
            transaction_id=tx.id,
            decision=decision,
            score=score,
            reason=reason,
            features=features,
            rules_triggered=rules_triggered,
            model_version=model_version,
            previous_hash=previous_hash,
        )

        audit = FraudDecisionAudit(
            transaction_id=tx.id,
            decision=decision,
            score=score,
            reason=reason,
            features=features,
            rules_triggered=rules_triggered,
            model_version=model_version,
            hash=record_hash,
            previous_hash=previous_hash,
        )
        session.add(audit)
        audit_records.append(audit)
        previous_hash = record_hash

    await session.flush()
    decision_counts = dict.fromkeys(("approve", "verify", "block"), 0)
    for r in audit_records:
        decision_counts[r.decision] = decision_counts.get(r.decision, 0) + 1
    print(
        f"Created {len(audit_records)} audit records "
        f"(approve={decision_counts['approve']}, "
        f"verify={decision_counts['verify']}, "
        f"block={decision_counts['block']})"
    )
    return audit_records


async def seed_data() -> None:
    """Main entry point for seeding development data.

    Per-table idempotency: each seed step checks its own table before inserting,
    so re-running fills whatever is missing without duplicating rows.
    """
    async with async_session_maker() as session:
        print("Starting seed (per-table idempotency)...")

        # 1. Users — get_or_create is idempotent; always returns all seed users
        users = await seed_users(session)
        if not users:
            # Fallback: fetch existing @example.com users
            result2 = await session.execute(
                select(User)
                .where(User.email.like("%@example.com"))
                .limit(SEED_USER_COUNT)
            )
            users = list(result2.scalars().all())
        if not users:
            print("No users available; aborting seed.")
            return

        # 2. Devices
        await seed_devices(session, users)

        # 3. Fraud rules (mix of active + inactive)
        await seed_fraud_rules(session)

        # 4. Transactions — returns existing rows if already present
        transactions = await seed_transactions(session, users)
        if not transactions:
            print("No transactions available; aborting seed.")
            return

        # 5. Fraud scores
        await seed_fraud_scores(session, transactions, users)

        # 6. Alerts (mix of severities/statuses including open)
        await seed_alerts(session, transactions, users)

        # 7. Blocked transactions
        await seed_blocked_transactions(session, transactions, users)

        # 8. Verification logs (includes PENDING for the default queue)
        await seed_verification_logs(session, transactions, users)

        # 9. Audit logs — NEW: populates fraud_decision_audits with valid hash chain
        await seed_audit_logs(session, transactions)

        await session.commit()
        print("Seed completed successfully.")


if __name__ == "__main__":
    asyncio.run(seed_data())
