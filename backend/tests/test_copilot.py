
"""
FraudShield AI v11 - Copilot Tests

Tests:
- Provider validation
- Missing API key handling
- Transaction privacy
- Screenshot validation
- Fraud Copilot response
- Automatic fallback metadata
- Provider monitoring access rules

No external AI API requests are made.
"""

import base64
import json
from types import SimpleNamespace

import pytest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import copilot
from app.db import Base, Transaction


# ============================================================
# TEST HELPERS
# ============================================================

def fake_actor():
    return SimpleNamespace(
        id="test-analyst-001",
        role="analyst",
    )


def fake_outcome():
    return {
        "text": "Review the evidence before making a decision.",
        "provider": "gemini",
        "model": "gemini-flash-lite-latest",
        "requested_provider": "auto",
        "fallback_used": False,
        "fallback_reason": None,
        "attempted_providers": ["gemini"],
    }


def fake_history(*args, **kwargs):
    return "test-history-001"


# ============================================================
# TEST 1 - MISSING PROVIDER KEY
# ============================================================

def test_missing_provider_key(monkeypatch):
    monkeypatch.delenv(
        "OPENAI_API_KEY",
        raising=False,
    )

    assert copilot.provider_key("openai") == ""

    with pytest.raises(
        copilot.ProviderFailure
    ) as error:
        copilot.generate_openai(
            "Explain this synthetic transaction."
        )

    assert error.value.reason == "not_configured"


# ============================================================
# TEST 2 - INVALID PROVIDER
# ============================================================

def test_unrecognized_provider_rejected():
    with pytest.raises(HTTPException) as error:
        copilot.provider_key("invalid")

    assert error.value.status_code == 422


# ============================================================
# TEST 3 - TRANSACTION PRIVACY
# ============================================================

def test_transaction_context_omits_upi_identifier():
    engine = create_engine(
        "sqlite:///:memory:"
    )

    Base.metadata.create_all(engine)

    with Session(engine) as db:
        transaction = Transaction(
            id="demo-txn-1",
            amount=7000,
            recipient_upi="private@upi",
            typical_amount=200,
            recent_count=3,
            hour=12,
            new_recipient=True,
            score=60,
            risk="MEDIUM",
            decision="WARN",
            reasons=json.dumps(["New recipient"]),
            model="rules",
            review_status="OPEN",
            reviewer_note="",
        )

        db.add(transaction)
        db.commit()

        result = copilot.transaction_context(
            db,
            "demo-txn-1",
        )

        assert result["amount_inr"] == 7000
        assert result["new_recipient"] is True

        # Raw recipient UPI ID must never be sent to AI.
        assert "recipient_upi" not in result
        assert "private@upi" not in json.dumps(result)

    engine.dispose()


# ============================================================
# TEST 4 - SCREENSHOT ANALYSIS
# ============================================================

def test_image_validation_no_external_call(monkeypatch):
    monkeypatch.setattr(
        copilot,
        "try_provider",
        lambda provider, prompt, image=None, **kwargs:
            "Advisory only",
    )

    monkeypatch.setattr(
        copilot,
        "save_ai_history",
        fake_history,
    )

    # Synthetic file with a PNG signature.
    image_bytes = (
        b"\x89PNG\r\n\x1a\n"
        + b"123456789012"
    )

    encoded = base64.b64encode(
        image_bytes
    ).decode("ascii")

    body = copilot.Screenshot(
        image_base64=encoded,
        mime_type="image/png",
        description="Synthetic scam example",
    )

    result = copilot.screenshot(
        body,
        actor=fake_actor(),
        db=None,
    )

    assert result["provider"] == "gemini"
    assert result["analysis"] == "Advisory only"
    assert result["history_id"] == "test-history-001"
    assert result["verified_fraud"] is False


# ============================================================
# TEST 5 - COPILOT ADVISORY RESPONSE
# ============================================================

def test_ask_result_advisory(monkeypatch):
    monkeypatch.setattr(
        copilot,
        "generate_with_fallback",
        lambda requested, prompt: fake_outcome(),
    )

    monkeypatch.setattr(
        copilot,
        "save_ai_history",
        fake_history,
    )

    body = copilot.Ask(
        question="Explain safe next steps",
        provider="auto",
    )

    result = copilot.ask(
        body,
        actor=fake_actor(),
        db=None,
    )

    assert result["provider"] == "gemini"
    assert result["fallback_used"] is False
    assert result["verified_fraud"] is False
    assert result["history_id"] == "test-history-001"
    assert "Review the evidence" in result["answer"]


# ============================================================
# TEST 6 - AUTOMATIC FALLBACK
# ============================================================

def test_automatic_fallback_to_groq(monkeypatch):
    attempts = []

    def fake_try_provider(
        provider,
        prompt,
        image=None,
        fallback_step=False,
    ):
        attempts.append((provider, fallback_step))

        if provider == "gemini":
            raise copilot.ProviderFailure(
                "gemini",
                status_code=503,
                reason="temporary_unavailable",
                retryable=True,
                fallback_allowed=True,
            )

        if provider == "groq":
            return "Groq successfully generated an answer."

        raise AssertionError(
            "Unexpected provider request"
        )

    monkeypatch.setattr(
        copilot,
        "try_provider",
        fake_try_provider,
    )

    result = copilot.generate_with_fallback(
        "auto",
        "Explain synthetic fraud risk indicators.",
    )

    assert result["provider"] == "groq"
    assert result["fallback_used"] is True

    assert result["attempted_providers"] == [
        "gemini",
        "groq",
    ]

    assert result["fallback_reason"] == (
        "temporary_unavailable"
    )

    assert attempts == [
        ("gemini", False),
        ("groq", True),
    ]


# ============================================================
# TEST 7 - SCREENSHOT MIME RESTRICTIONS
# ============================================================

def test_invalid_screenshot_type_rejected():
    body = copilot.Screenshot(
        image_base64="A" * 24,
        mime_type="application/pdf",
    )

    with pytest.raises(HTTPException) as error:
        copilot.screenshot(
            body,
            actor=fake_actor(),
            db=None,
        )

    assert error.value.status_code == 422


# ============================================================
# TEST 8 - PROVIDER STATUS METADATA
# ============================================================

def test_provider_status_contains_configuration():
    result = copilot.status(
        actor=fake_actor()
    )

    assert "configured" in result

    assert "gemini" in result["configured"]
    assert "groq" in result["configured"]
    assert "openai" in result["configured"]

    assert "automatic_order" in result

    # The endpoint must not return API key contents.
    assert "api_key" not in result
