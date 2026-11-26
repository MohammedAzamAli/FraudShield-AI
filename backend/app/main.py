from pathlib import Path as _EnvPath
from dotenv import load_dotenv
load_dotenv(_EnvPath(__file__).resolve().parents[1] / ".env")
import os
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "2")

"""FraudShield AI — Production-Inspired Financial Fraud Detection Platform.
Integrates Tabular ML Ensemble, PyTorch Deep Learning Anomaly & Sequence Networks,
Centralized Deterministic Policy Engine, Controlled 5-Agent Swarm, and Gemini Copilot.
"""
import json
import os
import re
import io
import csv
import hmac
import time
from dataclasses import replace
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
from typing import List, Dict, Any, Optional, Literal

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Header, Query
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select, func, inspect, text, bindparam, Time

from .db import (
    Base, engine, SessionLocal, Transaction, User, CaseAudit, CaseAssignment,
    RiskAssessment, AgentInvestigation, Customer, Beneficiary, RiskPolicyConfig
)
from .data_engine import (
    CUSTOMERS, BENEFICIARIES, get_or_create_customer, get_or_create_beneficiary,
    build_feature_vector, build_temporal_sequence_window
)
from .ml_engine import get_ml_engine
from .risk_engine import evaluate_transaction_risk, RiskEngineConfig, DEFAULT_CONFIG
from .agent_swarm import get_investigation_orchestrator
from .gemini_service import get_gemini_service
from .gemini_service import GeminiUnavailableError
from .simulation_engine import get_simulation_engine
from .security import current_user, require_role

app = FastAPI(
    title="FraudShield AI — Financial Fraud Detection Platform",
    description="Production-inspired financial fraud detection, deep learning anomaly scoring, multi-agent investigation, and explainable AI.",
    version="11.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure database tables exist
Base.metadata.create_all(bind=engine)
_transaction_column_migrations = {
    "input_context": "TEXT NOT NULL DEFAULT '{}'",
    "average_amount_30d": "FLOAT NOT NULL DEFAULT 2500.0",
    "transactions_last_24h": "INTEGER NOT NULL DEFAULT 1",
    "first_merchant_visit": "BOOLEAN NOT NULL DEFAULT FALSE",
    "payment_service_provider": "VARCHAR(40) NOT NULL DEFAULT 'Unspecified'",
    "merchant_category": "VARCHAR(60) NOT NULL DEFAULT 'General'",
    "transaction_state": "VARCHAR(40) NOT NULL DEFAULT 'Unspecified'",
    "device_os": "VARCHAR(20) NOT NULL DEFAULT 'Unknown'",
    "transaction_time": "TIME NULL",
    "screening_mode": "VARCHAR(20) NOT NULL DEFAULT 'balanced'",
    "screening_cutoff": "FLOAT NOT NULL DEFAULT 0.25",
}
_existing_transaction_columns = {column["name"] for column in inspect(engine).get_columns("transactions")}
_added_transaction_columns = _transaction_column_migrations.keys() - _existing_transaction_columns
if _added_transaction_columns:
    with engine.begin() as connection:
        for column_name in _added_transaction_columns:
            connection.execute(text(
                f"ALTER TABLE transactions ADD COLUMN {column_name} {_transaction_column_migrations[column_name]}"
            ))

    # Preserve context that earlier versions stored only in input_context JSON.
    _backfill = text("""
        UPDATE transactions SET
            average_amount_30d=:average_amount_30d,
            transactions_last_24h=:transactions_last_24h,
            first_merchant_visit=:first_merchant_visit,
            payment_service_provider=:payment_service_provider,
            merchant_category=:merchant_category,
            transaction_state=:transaction_state,
            device_os=:device_os,
            transaction_time=:transaction_time,
            screening_mode=:screening_mode,
            screening_cutoff=:screening_cutoff
        WHERE id=:id
    """).bindparams(bindparam("transaction_time", type_=Time()))
    with engine.begin() as connection:
        _legacy_rows = connection.execute(text("""
            SELECT id, input_context, channel, hour, typical_amount,
                   is_new_recipient, device_is_new, vpn_detected
            FROM transactions
            WHERE input_context IS NOT NULL AND input_context <> '{}'
        """)).mappings().all()
        for _row in _legacy_rows:
            try:
                _context = json.loads(_row["input_context"] or "{}")
            except (TypeError, ValueError):
                continue
            if not isinstance(_context, dict) or not _context:
                continue
            _time_value = _context.get("transaction_time") or f"{int(_row['hour'] or 0):02d}:00"
            try:
                _time_value = datetime.strptime(_time_value, "%H:%M").time()
            except (TypeError, ValueError):
                _time_value = None
            connection.execute(_backfill, {
                "id": _row["id"],
                "average_amount_30d": _context.get("average_amount_30d", _row["typical_amount"]),
                "transactions_last_24h": _context.get("transactions_last_24h", 1),
                "first_merchant_visit": _context.get("first_merchant_visit", _row["is_new_recipient"]),
                "payment_service_provider": _context.get("payment_service_provider", "Unspecified"),
                "merchant_category": _context.get("merchant_category", "General"),
                "transaction_state": _context.get("transaction_state", "Unspecified"),
                "device_os": _context.get("device_os", "Unknown"),
                "transaction_time": _time_value,
                "screening_mode": _context.get("screening_mode", "balanced"),
                "screening_cutoff": _context.get("screening_cutoff", 0.25),
            })

# Add the new query indexes to databases whose transactions table predates them.
for _index_name in ("idx_tx_flow_time", "idx_tx_category_time", "idx_tx_state_time"):
    next(index for index in Transaction.__table__.indexes if index.name == _index_name).create(engine, checkfirst=True)

def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------- Request Schemas -----------------
class PaymentRequest(BaseModel):
    amount: float = Field(gt=0, le=10000000)
    recipient_upi: str = Field(min_length=3, max_length=120)
    sender_upi: str = Field(default="rahul.sharma@okaxis", min_length=3, max_length=120)
    typical_amount: Optional[float] = Field(default=None, gt=0, le=10000000)
    recent_count: Optional[int] = Field(default=None, ge=0, le=100)
    hour: Optional[int] = Field(default=None, ge=0, le=23)
    new_recipient: Optional[bool] = Field(default=None)
    first_merchant_visit: Optional[bool] = Field(default=None)
    transactions_last_24h: int = Field(default=1, ge=0, le=500)
    payment_service_provider: str = Field(default="Unspecified", max_length=40)
    merchant_category: Optional[str] = Field(default=None, max_length=60)
    transaction_state: Optional[str] = Field(default=None, max_length=40)
    device_os: str = Field(default="Unknown", max_length=20)
    transaction_time: Optional[str] = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    screening_mode: str = Field(default="balanced", pattern=r"^(high|balanced|low|custom)$")
    screening_cutoff: float = Field(default=0.25, ge=0.0, le=1.0)
    channel: str = Field(default="UPI_P2P", max_length=30)
    device_is_new: bool = Field(default=False)
    vpn_detected: bool = Field(default=False)
    geo_flag: str = Field(default="normal")
    biometric_score: float = Field(default=0.92, ge=0.0, le=1.0)

class ReviewRequest(BaseModel):
    status: str = Field(pattern="^(OPEN|UNDER_REVIEW|CLOSED)$")
    note: str = Field(min_length=3, max_length=1000)

class QRRequest(BaseModel):
    uri: str = Field(min_length=5, max_length=2000)

class SimulationControl(BaseModel):
    interval_sec: float = Field(default=2.0, ge=0.2, le=10.0)
    scenario_mode: str = Field(default="MIXED") # MIXED, NORMAL, VELOCITY, ATO, MULE, PHISHING

class ScenarioInject(BaseModel):
    scenario: str = Field(pattern="^(NORMAL|VELOCITY|ATO|MULE|PHISHING)$")

class PolicyConfigUpdate(BaseModel):
    weight_ml: float = Field(ge=0.0, le=1.0)
    weight_dl_ae: float = Field(ge=0.0, le=1.0)
    weight_dl_seq: float = Field(ge=0.0, le=1.0)
    weight_behavioral: float = Field(ge=0.0, le=1.0)
    weight_velocity: float = Field(ge=0.0, le=1.0)
    weight_device: float = Field(ge=0.0, le=1.0)
    weight_beneficiary: float = Field(ge=0.0, le=1.0)
    thresh_low: int = Field(ge=5, le=50)
    thresh_medium: int = Field(ge=20, le=75)
    thresh_high: int = Field(ge=50, le=90)

# ----------------- Serialization Helper -----------------
def serialize_tx(t: Transaction, risk_assessment: Optional[RiskAssessment] = None) -> dict:
    reasons = json.loads(t.reasons) if (t.reasons and isinstance(t.reasons, str)) else (t.reasons or [])
    try:
        input_context = json.loads(t.input_context or "{}")
    except (TypeError, ValueError):
        input_context = {}
    data = {
        "id": t.id,
        "timestamp": t.timestamp.isoformat() if t.timestamp else None,
        "sender_upi": t.sender_upi,
        "sender_name": t.sender_name,
        "recipient_upi": t.recipient_upi,
        "recipient_name": t.recipient_name,
        "amount": t.amount,
        "channel": t.channel,
        "upi_flow": t.channel,
        "scenario_type": t.scenario_type,
        "hour": t.hour,
        "typical_amount": t.typical_amount,
        "average_amount_30d": t.average_amount_30d or t.typical_amount,
        "transactions_last_24h": t.transactions_last_24h,
        "first_merchant_visit": t.first_merchant_visit,
        "payment_service_provider": t.payment_service_provider,
        "merchant_category": t.merchant_category,
        "transaction_state": t.transaction_state,
        "device_os": t.device_os,
        "transaction_time": t.transaction_time.strftime("%H:%M") if t.transaction_time else input_context.get("transaction_time", f"{t.hour:02d}:00"),
        "screening_mode": t.screening_mode,
        "screening_cutoff": t.screening_cutoff,
        "input_context": input_context,
        "recent_count": t.recent_count_1h,
        "recent_count_1h": t.recent_count_1h,
        "time_since_last_sec": t.time_since_last_sec,
        "new_recipient": t.is_new_recipient,
        "is_new_recipient": t.is_new_recipient,
        "device_id": t.device_id,
        "device_is_new": t.device_is_new,
        "vpn_detected": t.vpn_detected,
        "geo_location_flag": t.geo_location_flag,
        "behavioral_biometric_score": t.behavioral_biometric_score,
        "risk_score": t.risk_score,
        "score": t.risk_score,
        "risk_tier": t.risk_tier,
        "risk": t.risk_tier,
        "decision": t.decision,
        "reasons": reasons,
        "review_status": t.review_status,
        "reviewer_note": t.reviewer_note,
        "assigned_to": t.assigned_to,
        "model": "production-ensemble-v1"
    }
    if risk_assessment:
        data["risk_assessment"] = {
            "ml_fraud_probability": risk_assessment.ml_fraud_probability,
            "dl_anomaly_score": risk_assessment.dl_anomaly_score,
            "dl_sequence_score": risk_assessment.dl_sequence_score,
            "behavioral_score": risk_assessment.behavioral_score,
            "velocity_score": risk_assessment.velocity_score,
            "device_score": risk_assessment.device_score,
            "beneficiary_score": risk_assessment.beneficiary_score,
            "consolidated_risk_score": risk_assessment.consolidated_risk_score,
            "decision": risk_assessment.decision
        }
    return data

# ----------------- Health & Metrics -----------------
@app.get("/api/health")
def health():
    models_dir = Path(__file__).resolve().parents[1] / "models"
    gemini = get_gemini_service()
    sim = get_simulation_engine()
    return {
        "status": "ok",
        "platform": "FraudShield AI Enterprise",
        "mode": "sandbox",
        "storage": "persistent",
        "version": "11.0.0",
        "models_loaded": {
            "ml_ensemble": (models_dir / "production_ml_pipeline.joblib").exists(),
            "dl_autoencoder": (models_dir / "production_dl_autoencoder.pt").exists(),
            "dl_sequence_gru": (models_dir / "production_dl_sequence.pt").exists()
        },
        "simulation_state": sim.state,
        "gemini_mode": "live" if gemini.is_live_configured() else "grounded_fallback"
    }

@app.get("/api/model/metrics")
def model_metrics():
    """Return the evaluation used by the simulator-aligned research model."""
    return _load_sandbox_metrics_report()


@app.get("/api/model/dataset-metrics")
def dataset_model_metrics():
    """Return the evaluation report for the labeled source dataset."""
    report_path = Path(__file__).resolve().parents[1] / "models" / "dataset_research_metrics.json"
    if not report_path.exists():
        return {
            "available": False,
            "message": "Run python ml/evaluate_dataset.py to create the dataset evaluation report.",
        }
    return json.loads(report_path.read_text())


def _load_sandbox_metrics_report():
    report_path = Path(__file__).resolve().parents[1] / "models" / "sandbox_metrics.json"
    if not report_path.exists():
        return {
            "available": False,
            "message": "Run python ml/train_sandbox.py to create the evaluation report."
        }

    report = json.loads(report_path.read_text())
    return {
        **report,
        "available": True,
        "confusion_matrix_labels": ["Legitimate", "Fraud"]
    }

@app.get("/api/ml/sandbox-metrics")
def sandbox_metrics():
    return _load_sandbox_metrics_report()

# ----------------- Core Ingestion & Analysis -----------------
CITY_STATE = {
    "mumbai": "Maharashtra", "bengaluru": "Karnataka", "bangalore": "Karnataka",
    "delhi": "Delhi", "pune": "Maharashtra", "hyderabad": "Telangana",
    "chennai": "Tamil Nadu", "kolkata": "West Bengal", "ahmedabad": "Gujarat",
    "jaipur": "Rajasthan"
}

def _transaction_geo_flag(customer, transaction_state: Optional[str], supplied_flag: str) -> str:
    if supplied_flag != "normal":
        return supplied_flag
    if not transaction_state:
        return supplied_flag
    home_state = CITY_STATE.get(str(getattr(customer, "home_city", "")).strip().lower())
    if home_state and transaction_state and home_state.casefold() != transaction_state.casefold():
        return "unusual"
    return supplied_flag

def _first_merchant_visit(req: PaymentRequest, customer, beneficiary) -> bool:
    if req.first_merchant_visit is not None:
        return req.first_merchant_visit
    if req.new_recipient is not None:
        return req.new_recipient
    return beneficiary.upi_id not in customer.trusted_beneficiaries

@app.post("/api/analyze")
async def analyze_payment(req: PaymentRequest, db: Session = Depends(db_session)):
    """Full-tier production risk analysis of an incoming transaction."""
    print("DEBUG 1: Starting analyze_payment", flush=True)
    sender_upi = req.sender_upi or "rahul.sharma@okaxis"
    customer = get_or_create_customer(sender_upi)
    beneficiary = get_or_create_beneficiary(req.recipient_upi)
    if req.merchant_category:
        beneficiary = replace(beneficiary, category=req.merchant_category)

    # Use supplied overrides or customer baseline defaults
    typical_amt = req.typical_amount if req.typical_amount is not None else customer.typical_amount
    customer = replace(customer, typical_amount=typical_amt)
    hour = req.hour if req.hour is not None else datetime.now(timezone.utc).hour
    freq = req.recent_count if req.recent_count is not None else customer.tx_count_last_1h + 1
    first_merchant_visit = _first_merchant_visit(req, customer, beneficiary)
    new_rec = first_merchant_visit
    geo_flag = _transaction_geo_flag(customer, req.transaction_state, req.geo_flag)

    print("DEBUG 2: Building features", flush=True)
    features_df = build_feature_vector(
        amount=req.amount,
        customer=customer,
        beneficiary=beneficiary,
        hour=hour,
        recent_count_1h=freq,
        time_since_last_sec=1800.0,
        is_new_recipient=new_rec,
        device_is_new=req.device_is_new,
        vpn_detected=req.vpn_detected,
        geo_flag=geo_flag,
        biometric_score=req.biometric_score
    )

    seq_window = build_temporal_sequence_window(customer, req.amount, features_df)

    # 1. Model Inference
    print("DEBUG 3: Running ML inference", flush=True)
    ml_engine = get_ml_engine()
    ml_output = ml_engine.predict_ml(features_df)
    print("DEBUG 4: Running DL AE inference", flush=True)
    dl_ae_output = ml_engine.predict_dl_anomaly(features_df)
    print("DEBUG 5: Running DL Seq inference", flush=True)
    dl_seq_output = ml_engine.predict_dl_sequence(seq_window)

    # 2. Centralized Risk Engine
    print("DEBUG 6: Evaluating risk engine", flush=True)
    risk_res = evaluate_transaction_risk(
        features=features_df,
        customer=customer,
        beneficiary=beneficiary,
        ml_output=ml_output,
        dl_ae_output=dl_ae_output,
        dl_seq_output=dl_seq_output,
        transactions_last_24h=req.transactions_last_24h,
        first_merchant_visit=first_merchant_visit,
        channel=req.channel
    )

    tx_id = str(uuid4())
    now = datetime.now(timezone.utc)
    review_status = "OPEN" if risk_res["risk_tier"] in ["HIGH", "CRITICAL"] else "CLOSED"

    # 3. Multi-Agent Investigation if High/Critical
    agent_inv_res = None
    if risk_res["risk_tier"] in ["HIGH", "CRITICAL"]:
        print("DEBUG 7: Running agent investigation", flush=True)
        orchestrator = get_investigation_orchestrator()
        tx_dict = {
            "id": tx_id, "amount": req.amount, "recipient_upi": req.recipient_upi,
            "sender_upi": customer.upi_id, "hour": hour, "recent_count": freq,
            "channel": req.channel, "device_is_new": req.device_is_new,
            "vpn_detected": req.vpn_detected, "behavioral_biometric_score": req.biometric_score,
            "transactions_last_24h": req.transactions_last_24h,
            "payment_service_provider": req.payment_service_provider,
            "merchant_category": req.merchant_category or beneficiary.category,
            "transaction_state": req.transaction_state or "Unspecified",
            "device_os": req.device_os
        }
        agent_inv_res = orchestrator.run_investigation(
            tx_data=tx_dict, risk_result=risk_res, customer=customer, beneficiary=beneficiary
        )

    # 4. Database Persistence
    print("DEBUG 8: Saving to database", flush=True)
    tx = Transaction(
        id=tx_id,
        timestamp=now,
        sender_upi=customer.upi_id,
        sender_name=customer.name,
        recipient_upi=beneficiary.upi_id,
        recipient_name=beneficiary.name,
        amount=req.amount,
        channel=req.channel,
        scenario_type="user_manual_submission",
        hour=hour,
        typical_amount=typical_amt,
        average_amount_30d=typical_amt,
        transactions_last_24h=req.transactions_last_24h,
        first_merchant_visit=first_merchant_visit,
        payment_service_provider=req.payment_service_provider,
        merchant_category=req.merchant_category or beneficiary.category,
        transaction_state=req.transaction_state or "Unspecified",
        device_os=req.device_os,
        transaction_time=datetime.strptime(req.transaction_time or f"{hour:02d}:00", "%H:%M").time(),
        screening_mode=req.screening_mode,
        screening_cutoff=req.screening_cutoff,
        input_context=json.dumps({
            "transactions_last_24h": req.transactions_last_24h,
            "average_amount_30d": typical_amt,
            "new_device": req.device_is_new,
            "first_merchant_visit": first_merchant_visit,
            "vpn_ip": req.vpn_detected,
            "payment_service_provider": req.payment_service_provider,
            "upi_flow": req.channel,
            "merchant_category": req.merchant_category or beneficiary.category,
            "transaction_state": req.transaction_state or "Unspecified",
            "device_os": req.device_os,
            "transaction_time": req.transaction_time or f"{hour:02d}:00",
            "geo_assessment": geo_flag,
            "screening_mode": req.screening_mode,
            "screening_cutoff": req.screening_cutoff
        }),
        recent_count_1h=freq,
        time_since_last_sec=1800.0,
        is_new_recipient=new_rec,
        device_id=customer.primary_device_id if not req.device_is_new else f"DEV-{uuid4().hex[:6].upper()}",
        device_is_new=req.device_is_new,
        vpn_detected=req.vpn_detected,
        geo_location_flag=geo_flag,
        behavioral_biometric_score=req.biometric_score,
        risk_score=risk_res["consolidated_risk_score"],
        risk_tier=risk_res["risk_tier"],
        decision=risk_res["decision"],
        reasons=json.dumps(risk_res["reasons"]),
        review_status=review_status
    )
    db.add(tx)

    risk_record = RiskAssessment(
        transaction_id=tx_id,
        ml_fraud_probability=risk_res["layer_breakdown"]["ml_fraud_probability"],
        dl_anomaly_score=risk_res["layer_breakdown"]["dl_anomaly_score"],
        dl_sequence_score=risk_res["layer_breakdown"]["dl_sequence_score"],
        behavioral_score=risk_res["layer_breakdown"]["behavioral_score"],
        velocity_score=risk_res["layer_breakdown"]["velocity_score"],
        device_score=risk_res["layer_breakdown"]["device_score"],
        beneficiary_score=risk_res["layer_breakdown"]["beneficiary_score"],
        consolidated_risk_score=risk_res["consolidated_risk_score"],
        decision=risk_res["decision"],
        explanation_json=json.dumps(risk_res["reasons"])
    )
    db.add(risk_record)

    if agent_inv_res:
        db.add(AgentInvestigation(
            id=agent_inv_res["case_id"],
            transaction_id=tx_id,
            status="INVESTIGATING",
            priority=risk_res["risk_tier"],
            triggered_reason="; ".join(risk_res["reasons"][:2]),
            synthesis_report=agent_inv_res["dossier_summary"],
            agent_timeline_json=json.dumps(agent_inv_res["timeline"])
        ))

    db.commit()
    db.refresh(tx)

    result = serialize_tx(tx, risk_record)
    result["agent_investigation"] = agent_inv_res
    result["layer_breakdown"] = risk_res["layer_breakdown"]

    # Broadcast over WebSockets
    sim = get_simulation_engine()
    await sim.broadcast_event("transaction", result)
    if agent_inv_res:
        await sim.broadcast_event("agent_investigation", agent_inv_res)

    return result

@app.post("/api/ml/sandbox-predict")
def sandbox_predict(req: PaymentRequest):
    """Production ML + DL probability comparison endpoint."""
    customer = get_or_create_customer(req.sender_upi or "rahul.sharma@okaxis")
    if req.typical_amount is not None:
        customer = replace(customer, typical_amount=req.typical_amount)
    beneficiary = get_or_create_beneficiary(req.recipient_upi)
    if req.merchant_category:
        beneficiary = replace(beneficiary, category=req.merchant_category)
    geo_flag = _transaction_geo_flag(customer, req.transaction_state, req.geo_flag)
    first_merchant_visit = _first_merchant_visit(req, customer, beneficiary)
    features_df = build_feature_vector(
        amount=req.amount,
        customer=customer,
        beneficiary=beneficiary,
        hour=req.hour if req.hour is not None else 12,
        recent_count_1h=req.recent_count if req.recent_count is not None else 1,
        time_since_last_sec=1800.0,
        is_new_recipient=first_merchant_visit,
        device_is_new=req.device_is_new,
        vpn_detected=req.vpn_detected,
        geo_flag=geo_flag,
        biometric_score=req.biometric_score
    )
    seq_window = build_temporal_sequence_window(customer, req.amount, features_df)
    ml_engine = get_ml_engine()
    ml_res = ml_engine.predict_ml(features_df)
    dl_ae = ml_engine.predict_dl_anomaly(features_df)
    dl_seq = ml_engine.predict_dl_sequence(seq_window)

    return {
        "model": "Ensemble (Random Forest 40%, HistGradientBoosting 45%, Logistic Regression 15%)",
        "estimated_synthetic_label_probability": ml_res["ensemble_fraud_probability"],
        "dl_anomaly_score": dl_ae["dl_anomaly_score"],
        "dl_sequence_score": dl_seq["dl_sequence_risk_score"],
        "research_threshold": ml_res["optimal_threshold"],
        "research_flag": ml_res["flagged"],
        "models_breakdown": {
            "random_forest": ml_res["random_forest_prob"],
            "hist_gradient_boosting": ml_res["hist_gradient_boosting_prob"],
            "logistic_regression": ml_res["logistic_regression_prob"]
        },
        "warning": "Experimental probability trained on synthetic sandbox labels; it is not calibrated against verified real-world fraud outcomes."
    }

# ----------------- Transactions & Analytics -----------------
@app.get("/api/transactions")
def get_transactions(limit: int = 100, db: Session = Depends(db_session)):
    limit = max(1, min(limit, 500))
    items = db.execute(select(Transaction).order_by(Transaction.timestamp.desc()).limit(limit)).scalars().all()
    return [serialize_tx(t) for t in items]

@app.get("/api/transactions/{transaction_id}")
def get_transaction_detail(transaction_id: str, db: Session = Depends(db_session)):
    t = db.get(Transaction, transaction_id)
    if not t:
        raise HTTPException(404, "Transaction not found")
    risk_record = db.get(RiskAssessment, transaction_id)
    inv = db.execute(select(AgentInvestigation).where(AgentInvestigation.transaction_id == transaction_id)).scalar_one_or_none()
    res = serialize_tx(t, risk_record)
    if inv:
        res["agent_investigation"] = {
            "id": inv.id,
            "status": inv.status,
            "priority": inv.priority,
            "triggered_reason": inv.triggered_reason,
            "synthesis_report": inv.synthesis_report,
            "timeline": json.loads(inv.agent_timeline_json) if inv.agent_timeline_json else []
        }
    return res

@app.get("/api/summary")
def get_summary(db: Session = Depends(db_session)):
    items = db.execute(select(Transaction)).scalars().all()
    c = Counter(t.risk_tier for t in items)
    # Also support legacy 'risk' column if populated
    for t in items:
        if not t.risk_tier and hasattr(t, 'risk') and t.risk:
            c[t.risk] += 1
            
    total_vol = sum(t.amount for t in items)
    blocked_vol = sum(t.amount for t in items if t.decision == "BLOCK")
    return {
        "total": len(items),
        "high": c["HIGH"] + c["CRITICAL"],
        "critical": c["CRITICAL"],
        "medium": c["MEDIUM"],
        "low": c["LOW"],
        "open_cases": sum(t.review_status == "OPEN" for t in items),
        "total_volume": round(total_vol, 2),
        "blocked_volume": round(blocked_vol, 2),
        "fraud_rate": round(((c["HIGH"] + c["CRITICAL"]) / max(1, len(items))) * 100, 2)
    }

@app.get("/api/analytics")
def get_analytics(db: Session = Depends(db_session)):
    items = db.execute(select(Transaction)).scalars().all()
    by_day = {}
    for t in items:
        day = t.timestamp.date().isoformat()
        entry = by_day.setdefault(day, {"date": day, "total": 0, "high": 0, "medium": 0, "low": 0, "volume": 0.0})
        entry["total"] += 1
        tier_key = t.risk_tier.lower() if t.risk_tier else "low"
        if tier_key == "critical": tier_key = "high"
        entry[tier_key] = entry.get(tier_key, 0) + 1
        entry["volume"] += t.amount

    daily = sorted(by_day.values(), key=lambda x: x["date"])[-30:]
    for e in daily: e["volume"] = round(e["volume"], 2)

    risks = Counter(t.risk_tier for t in items)
    return {
        "daily": daily,
        "risk_distribution": {
            "CRITICAL": risks["CRITICAL"],
            "HIGH": risks["HIGH"],
            "MEDIUM": risks["MEDIUM"],
            "LOW": risks["LOW"]
        },
        "total": len(items),
        "total_volume": round(sum(t.amount for t in items), 2),
        "average_risk_score": round(sum(t.risk_score for t in items) / max(1, len(items)), 1),
        "review_open": sum(t.review_status == "OPEN" for t in items),
        "review_in_progress": sum(t.review_status == "UNDER_REVIEW" for t in items),
        "note": "Production risk intelligence analytics aggregated across live simulated event streams."
    }

@app.get("/api/insights")
def get_insights(db: Session = Depends(db_session)):
    items = db.execute(select(Transaction).order_by(Transaction.timestamp.desc()).limit(500)).scalars().all()
    by_hour = Counter(t.hour for t in items)
    return {
        "hourly": [{"hour": h, "count": by_hour[h]} for h in range(24)],
        "risk": dict(Counter(t.risk_tier for t in items)),
        "recent_high": [serialize_tx(t) for t in items if t.risk_tier in ["HIGH", "CRITICAL"]][:8]
    }

# ----------------- Real-Time Simulation Stream Controls -----------------
@app.get("/api/simulation/status")
def simulation_status():
    return get_simulation_engine().get_status()

@app.post("/api/simulation/start")
async def simulation_start(ctrl: SimulationControl = SimulationControl()):
    sim = get_simulation_engine()
    await sim.start(interval_sec=ctrl.interval_sec, scenario_mode=ctrl.scenario_mode)
    return sim.get_status()

@app.post("/api/simulation/pause")
async def simulation_pause():
    sim = get_simulation_engine()
    await sim.pause()
    return sim.get_status()

@app.post("/api/simulation/resume")
async def simulation_resume():
    sim = get_simulation_engine()
    await sim.resume()
    return sim.get_status()

@app.post("/api/simulation/stop")
async def simulation_stop():
    sim = get_simulation_engine()
    await sim.stop()
    return sim.get_status()

@app.post("/api/simulation/inject")
async def simulation_inject(body: ScenarioInject):
    sim = get_simulation_engine()
    event = sim.generate_single_event(scenario_override=body.scenario)
    await sim.broadcast_event("transaction", event["transaction"])
    if event["agent_investigation"]:
        await sim.broadcast_event("agent_investigation", event["agent_investigation"])
    return event

# ----------------- WebSockets -----------------
@app.websocket("/ws/stream")
@app.websocket("/ws/alerts")
async def websocket_endpoint(ws: WebSocket):
    sim = get_simulation_engine()
    await ws.accept()
    await sim.register_websocket(ws)
    try:
        while True:
            # Keep-alive loop
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        sim.unregister_websocket(ws)

# ----------------- Investigation Center & Case Management -----------------
@app.get("/api/cases")
def get_cases(db: Session = Depends(db_session)):
    items = db.execute(
        select(Transaction)
        .where(Transaction.risk_tier.in_(["HIGH", "CRITICAL"]))
        .order_by(Transaction.timestamp.desc())
    ).scalars().all()
    return [serialize_tx(t) for t in items]

@app.get("/api/agents/activity")
def get_agent_activity(limit: int = 20, db: Session = Depends(db_session)):
    invs = db.execute(select(AgentInvestigation).order_by(AgentInvestigation.created_at.desc()).limit(limit)).scalars().all()
    results = []
    for inv in invs:
        results.append({
            "case_id": inv.id,
            "transaction_id": inv.transaction_id,
            "status": inv.status,
            "priority": inv.priority,
            "triggered_reason": inv.triggered_reason,
            "synthesis_report": inv.synthesis_report,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
            "timeline": json.loads(inv.agent_timeline_json) if inv.agent_timeline_json else []
        })
    return results

@app.post("/api/cases/{transaction_id}/investigate")
def run_manual_agent_investigation(transaction_id: str, db: Session = Depends(db_session)):
    t = db.get(Transaction, transaction_id)
    if not t:
        raise HTTPException(404, "Transaction not found")
    customer = get_or_create_customer(t.sender_upi)
    beneficiary = get_or_create_beneficiary(t.recipient_upi)
    risk_record = db.get(RiskAssessment, transaction_id)

    orchestrator = get_investigation_orchestrator()
    risk_dict = {
        "consolidated_risk_score": t.risk_score,
        "risk_tier": t.risk_tier,
        "decision": t.decision,
        "layer_breakdown": {
            "ml_fraud_probability": risk_record.ml_fraud_probability if risk_record else 0.5,
            "dl_anomaly_score": risk_record.dl_anomaly_score if risk_record else 0.5,
            "dl_sequence_score": risk_record.dl_sequence_score if risk_record else 0.5
        }
    }
    tx_dict = serialize_tx(t)
    result = orchestrator.run_investigation(tx_dict, risk_dict, customer, beneficiary)
    
    # Save investigation
    db.add(AgentInvestigation(
        id=result["case_id"],
        transaction_id=t.id,
        status="INVESTIGATING",
        priority=t.risk_tier,
        triggered_reason="Manual analyst agent investigation trigger",
        synthesis_report=result["dossier_summary"],
        agent_timeline_json=json.dumps(result["timeline"])
    ))
    db.commit()
    return result

# ----------------- Customer & Beneficiary Profiles -----------------
@app.get("/api/customers")
def list_customers():
    return [
        {
            "id": c.id, "name": c.name, "upi_id": c.upi_id,
            "typical_amount": c.typical_amount, "daily_spending_limit": c.daily_spending_limit,
            "daily_spent_today": round(c.daily_spent_today, 2),
            "typical_hours": f"{c.typical_hour_start:02d}:00 - {c.typical_hour_end:02d}:00",
            "social_trust_score": c.social_trust_score,
            "home_city": c.home_city, "primary_device": c.primary_device_id
        }
        for c in CUSTOMERS.values()
    ]

@app.get("/api/beneficiaries")
def list_beneficiaries():
    return [
        {
            "id": b.id, "name": b.name, "upi_id": b.upi_id,
            "category": b.category, "verification_status": b.verification_status,
            "is_blacklisted": b.is_blacklisted, "fraud_complaints_count": b.fraud_complaints_count
        }
        for b in BENEFICIARIES.values()
    ]

# ----------------- Policy & Settings Engine -----------------
@app.get("/api/policy/config")
def get_policy_config():
    return {
        "weights": {
            "ml": DEFAULT_CONFIG.weight_ml,
            "dl_ae": DEFAULT_CONFIG.weight_dl_ae,
            "dl_seq": DEFAULT_CONFIG.weight_dl_seq,
            "behavioral": DEFAULT_CONFIG.weight_behavioral,
            "velocity": DEFAULT_CONFIG.weight_velocity,
            "device": DEFAULT_CONFIG.weight_device,
            "beneficiary": DEFAULT_CONFIG.weight_beneficiary
        },
        "thresholds": {
            "low": DEFAULT_CONFIG.thresh_low,
            "medium": DEFAULT_CONFIG.thresh_medium,
            "high": DEFAULT_CONFIG.thresh_high
        },
        "hard_stops": {
            "blacklist": DEFAULT_CONFIG.hard_stop_blacklist,
            "daily_limit": DEFAULT_CONFIG.hard_stop_daily_limit
        }
    }

@app.post("/api/policy/config")
def update_policy_config(cfg: PolicyConfigUpdate):
    total_weights = (cfg.weight_ml + cfg.weight_dl_ae + cfg.weight_dl_seq + 
                     cfg.weight_behavioral + cfg.weight_velocity + 
                     cfg.weight_device + cfg.weight_beneficiary)
    if not (0.95 <= total_weights <= 1.05):
        raise HTTPException(422, f"Weights must sum to approximately 1.0 (got {total_weights:.2f})")
    
    DEFAULT_CONFIG.weight_ml = cfg.weight_ml
    DEFAULT_CONFIG.weight_dl_ae = cfg.weight_dl_ae
    DEFAULT_CONFIG.weight_dl_seq = cfg.weight_dl_seq
    DEFAULT_CONFIG.weight_behavioral = cfg.weight_behavioral
    DEFAULT_CONFIG.weight_velocity = cfg.weight_velocity
    DEFAULT_CONFIG.weight_device = cfg.weight_device
    DEFAULT_CONFIG.weight_beneficiary = cfg.weight_beneficiary
    DEFAULT_CONFIG.thresh_low = cfg.thresh_low
    DEFAULT_CONFIG.thresh_medium = cfg.thresh_medium
    DEFAULT_CONFIG.thresh_high = cfg.thresh_high
    return {"status": "updated", "config": get_policy_config()}

# ----------------- QR Inspector -----------------
@app.post("/api/qr/inspect")
def inspect_qr(req: QRRequest):
    from urllib.parse import urlsplit, parse_qs
    u = urlsplit(req.uri)
    if u.scheme.lower() != "upi" or u.netloc.lower() != "pay":
        raise HTTPException(422, "Not a valid UPI pay URI")
    args = parse_qs(u.query, keep_blank_values=True)
    payee = args.get("pa", [""])[0]
    if not re.fullmatch(r"[A-Za-z0-9._-]+@[A-Za-z0-9.-]+", payee):
        raise HTTPException(422, "Invalid payee VPA")
    
    amount = args.get("am", [""])[0]
    warnings = []
    if amount:
        try:
            a = float(amount)
            if not 0 < a <= 1000000: raise ValueError()
        except ValueError:
            raise HTTPException(422, "Invalid amount")
            
    payee_name = args.get("pn", [""])[0]
    if not payee_name:
        warnings.append("Payee name missing; independently verify recipient identity")
        
    ben = BENEFICIARIES.get(payee)
    is_blacklisted = False
    if ben and ben.is_blacklisted:
        is_blacklisted = True
        warnings.append("ALERT: Payee VPA is flagged on national fraud blacklist!")
    elif any(w in payee.lower() for w in ["crypto", "reward", "lottery", "cashback"]):
        warnings.append("Payee VPA contains high-risk promotional scam keywords")

    return {
        "payee": payee,
        "payee_name": payee_name,
        "amount": amount or None,
        "is_blacklisted": is_blacklisted,
        "warnings": warnings,
        "verified": ben is not None and ben.verification_status == "verified",
        "note": "QR inspector parses payload and matches against fraud blacklist registry."
    }

# ----------------- Gemini Copilot Service Routes -----------------
class AIChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1200)

class AIChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1200)
    transaction_id: Optional[str] = Field(default=None, max_length=80)
    language: str = "English"
    history: List[AIChatMessage] = Field(default_factory=list, max_length=12)

class AIScreenshotRequest(BaseModel):
    image_base64: str = Field(min_length=20)
    mime_type: str = "image/png"
    description: str = ""

class AIReportRequest(BaseModel):
    transaction_id: str = Field(min_length=4, max_length=80)
    analyst_notes: str = Field(default="", max_length=1500)

def _live_gemini(method, *args, **kwargs):
    try:
        return method(*args, require_live=True, **kwargs)
    except GeminiUnavailableError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc

def _ai_transaction_context(t: Transaction) -> dict:
    """Pass only minimal, simulated risk evidence to Gemini; omit IDs and names."""
    return {
        "simulated": True,
        "amount_inr": t.amount,
        "hour": t.hour,
        "typical_amount_inr": t.typical_amount,
        "transactions_last_hour": t.recent_count_1h,
        "new_recipient": t.is_new_recipient,
        "device_is_new": t.device_is_new,
        "vpn_detected": t.vpn_detected,
        "risk_score": t.risk_score,
        "risk_level": t.risk_tier,
        "decision": t.decision,
        "risk_reasons": json.loads(t.reasons or "[]"),
        "review_status": t.review_status
    }

@app.get("/api/ai/status")
def ai_status():
    gemini = get_gemini_service()
    return {
        "provider": "Google Gemini",
        "configured": gemini.is_live_configured(),
        "active_gemini_model": gemini.model,
        "mode": "ready" if gemini.is_live_configured() else "needs_configuration",
        "calls_made": gemini.call_count,
        "last_error": gemini.last_error,
        "last_error_status": gemini.last_error_status if gemini.last_error else None,
        "note": "Copilot requests are sent only to Google Gemini; no local model fallback is used."
    }

@app.post("/api/ai/ask")
def ai_ask(body: AIChatRequest, actor=Depends(current_user), db: Session = Depends(db_session)):
    gemini = get_gemini_service()
    tx_data = None
    if body.transaction_id:
        if actor.role not in ("admin", "analyst"):
            raise HTTPException(403, "Transaction context is available to analysts only")
        t = db.get(Transaction, body.transaction_id)
        if not t:
            raise HTTPException(404, "Transaction not found")
        tx_data = _ai_transaction_context(t)
    history = [message.model_dump() for message in body.history]
    return _live_gemini(
        gemini.chat_assistant,
        body.question,
        context_tx=tx_data,
        language=body.language,
        history=history
    )

@app.post("/api/ai/explain")
def ai_explain(body: AIChatRequest, actor=Depends(require_role("admin", "analyst")), db: Session = Depends(db_session)):
    if not body.transaction_id:
        raise HTTPException(422, "transaction_id is required")
    t = db.get(Transaction, body.transaction_id)
    if not t:
        raise HTTPException(404, "Transaction not found")
    gemini = get_gemini_service()
    return _live_gemini(gemini.explain_transaction, _ai_transaction_context(t), language=body.language)

@app.post("/api/ai/report")
def ai_report(body: AIReportRequest, actor=Depends(require_role("admin", "analyst")), db: Session = Depends(db_session)):
    t = db.get(Transaction, body.transaction_id)
    if not t:
        raise HTTPException(404, "Transaction not found")
    gemini = get_gemini_service()
    return _live_gemini(gemini.generate_investigation_report, _ai_transaction_context(t), analyst_notes=body.analyst_notes)

@app.post("/api/ai/screenshot")
def ai_screenshot(body: AIScreenshotRequest, actor=Depends(require_role("admin", "analyst"))):
    gemini = get_gemini_service()
    return _live_gemini(gemini.analyze_screenshot, body.image_base64, body.mime_type, body.description)

# ----------------- Backward Compatibility Helpers -----------------
def load_sandbox_model():
    import joblib
    path = Path(__file__).resolve().parents[1] / "models" / "sandbox_pipeline.joblib"
    if not path.exists():
        path = Path(__file__).resolve().parents[1] / "models" / "production_ml_pipeline.joblib"
    return joblib.load(path)

# ----------------- Include Advanced & Network Routers -----------------
from .advanced import router as advanced_router
app.include_router(advanced_router)

from .network import router as network_router
app.include_router(network_router)

# Provide fallback legacy admin review endpoint
@app.patch("/api/cases/{transaction_id}")
def legacy_case_review(transaction_id: str, review: ReviewRequest, db: Session = Depends(db_session)):
    t = db.get(Transaction, transaction_id)
    if not t:
        raise HTTPException(404, "Case not found")
    t.review_status = review.status
    t.reviewer_note = review.note
    db.commit()
    db.refresh(t)
    return serialize_tx(t)
