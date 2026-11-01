
"""
FraudShield AI v11 - Phase 3
Persistent AI provider monitoring.

Stores request metadata only.
Never stores API keys, prompts, images, or AI responses.
"""

import logging
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    select,
)
from sqlalchemy.exc import SQLAlchemyError

from .db import Base, SessionLocal, engine


logger = logging.getLogger(__name__)

PROVIDERS = ("gemini", "groq", "openai")

_table_lock = Lock()
_table_ready = False


class AIProviderAttempt(Base):
    __tablename__ = "ai_provider_attempts"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    provider = Column(
        String(32),
        nullable=False,
        index=True,
    )

    model_name = Column(
        String(120),
        nullable=False,
    )

    success = Column(
        Boolean,
        nullable=False,
    )

    status_code = Column(
        Integer,
        nullable=True,
    )

    error_reason = Column(
        String(64),
        nullable=True,
    )

    latency_ms = Column(
        Float,
        nullable=False,
    )

    fallback_step = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


def ensure_monitoring_table():
    """Create only the monitoring table if missing."""

    global _table_ready

    if _table_ready:
        return

    with _table_lock:
        if _table_ready:
            return

        Base.metadata.create_all(
            bind=engine,
            tables=[AIProviderAttempt.__table__],
            checkfirst=True,
        )

        _table_ready = True


def record_attempt(
    provider,
    model_name,
    success,
    latency_ms,
    status_code=None,
    error_reason=None,
    fallback_step=False,
):
    """
    Record one actual request attempt.

    Logging failures do not interrupt AI generation.
    """

    if provider not in PROVIDERS:
        return

    allowed_reasons = {
        "not_configured",
        "credits_exhausted",
        "temporary_unavailable",
        "connection_error",
        "access_or_request_error",
        "invalid_response",
        "empty_response",
        "unknown_error",
    }

    safe_reason = (
        error_reason
        if error_reason in allowed_reasons
        else "unknown_error"
    ) if not success else None

    try:
        ensure_monitoring_table()

        with SessionLocal() as db:
            item = AIProviderAttempt(
                provider=provider,
                model_name=str(model_name)[:120],
                success=bool(success),
                status_code=status_code,
                error_reason=safe_reason,
                latency_ms=max(
                    0.0,
                    round(float(latency_ms), 2),
                ),
                fallback_step=bool(fallback_step),
            )

            db.add(item)
            db.commit()

    except SQLAlchemyError:
        logger.warning(
            "Could not persist AI monitoring event",
            exc_info=False,
        )


def utc_datetime(value):
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def get_monitoring_summary(configured_map):
    """
    Return a bounded monitoring snapshot.

    The 24-hour metrics use the latest 5000 attempts.
    No sensitive content is returned.
    """

    ensure_monitoring_table()

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    recent_cutoff = now - timedelta(minutes=30)

    with SessionLocal() as db:
        rows = db.execute(
            select(AIProviderAttempt)
            .where(AIProviderAttempt.created_at >= cutoff)
            .order_by(
                AIProviderAttempt.created_at.desc()
            )
            .limit(5000)
        ).scalars().all()

    result = []

    for provider in PROVIDERS:
        items = [
            row
            for row in rows
            if row.provider == provider
        ]

        successes = [
            item for item in items if item.success
        ]

        failures = [
            item for item in items if not item.success
        ]

        recent = [
            item
            for item in items
            if (
                utc_datetime(item.created_at)
                >= recent_cutoff
            )
        ]

        total = len(items)
        success_count = len(successes)
        failure_count = len(failures)

        avg_latency = (
            round(
                sum(item.latency_ms for item in items)
                / total,
                1,
            )
            if total
            else None
        )

        fallback_successes = sum(
            1
            for item in items
            if item.fallback_step and item.success
        )

        last = items[0] if items else None
        last_error = next(
            (item for item in items if not item.success),
            None,
        )

        if not configured_map.get(provider):
            health = "not_configured"

        elif not recent:
            health = "unknown"

        elif recent[0].success:
            health = "operational"

        elif recent[0].error_reason == "credits_exhausted":
            health = "billing_issue"

        elif recent[0].error_reason == "access_or_request_error":
            health = "access_issue"

        elif any(item.success for item in recent):
            health = "degraded"

        else:
            health = "unavailable"

        reasons = {}

        for item in failures:
            reason = item.error_reason or "unknown_error"
            reasons[reason] = reasons.get(reason, 0) + 1

        result.append({
            "provider": provider,
            "configured": bool(
                configured_map.get(provider)
            ),
            "health": health,
            "requests": total,
            "successes": success_count,
            "failures": failure_count,
            "success_rate": (
                round(100 * success_count / total, 1)
                if total else None
            ),
            "average_latency_ms": avg_latency,
            "successful_fallbacks": fallback_successes,
            "last_request_at": (
                utc_datetime(last.created_at).isoformat()
                if last else None
            ),
            "last_error_reason": (
                last_error.error_reason
                if last_error else None
            ),
            "error_counts": reasons,
        })

    activity = []

    for row in rows[:30]:
        activity.append({
            "id": row.id,
            "provider": row.provider,
            "model_name": row.model_name,
            "success": bool(row.success),
            "status_code": row.status_code,
            "error_reason": row.error_reason,
            "latency_ms": round(row.latency_ms, 1),
            "fallback_step": bool(row.fallback_step),
            "created_at": utc_datetime(
                row.created_at
            ).isoformat(),
        })

    return {
        "window_hours": 24,
        "generated_at": now.isoformat(),
        "monitored_attempts": len(rows),
        "providers": result,
        "recent_activity": activity,
        "note": (
            "Health is inferred from recent recorded requests, "
            "not a continuous external availability probe. "
            "Metrics are limited to the latest 5000 attempts "
            "in the last 24 hours."
        ),
    }
