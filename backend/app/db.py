"""Production-Grade Database Architecture for Fraud Shield AI.
Supports both SQLite (default single-click development) and PostgreSQL (production).
Indexed for high-throughput transaction streaming and structured investigation records.
"""
import os
import json
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (
    create_engine, Column, String, Float, Integer, Boolean,
    DateTime, Time, Text, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fraudshield.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

def utcnow():
    return datetime.now(timezone.utc)

class Customer(Base):
    __tablename__ = "customers"
    id = Column(String(64), primary_key=True) # e.g. "CUST-1049"
    name = Column(String(120), nullable=False)
    upi_id = Column(String(120), unique=True, index=True, nullable=False)
    account_age_days = Column(Integer, default=365)
    daily_spending_limit = Column(Float, default=100000.0)
    typical_amount = Column(Float, default=2500.0)
    typical_hour_start = Column(Integer, default=7)
    typical_hour_end = Column(Integer, default=22)
    social_trust_score = Column(Float, default=0.85)
    past_fraud_flags = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow)

class Beneficiary(Base):
    __tablename__ = "beneficiaries"
    id = Column(String(64), primary_key=True)
    upi_id = Column(String(120), unique=True, index=True, nullable=False)
    name = Column(String(120), nullable=False)
    category = Column(String(60), default="P2P")
    verification_status = Column(String(30), default="verified") # verified, recently_registered, suspicious
    is_blacklisted = Column(Boolean, default=False)
    fraud_complaints_count = Column(Integer, default=0)
    total_inflow = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), default=utcnow)

class Device(Base):
    __tablename__ = "devices"
    id = Column(String(64), primary_key=True) # Fingerprint ID e.g. "DEV-98421"
    customer_id = Column(String(64), ForeignKey("customers.id"), nullable=True)
    ip_address = Column(String(45), default="127.0.0.1")
    location_city = Column(String(80), default="Mumbai")
    vpn_proxy_detected = Column(Boolean, default=False)
    is_trusted = Column(Boolean, default=True)
    last_seen = Column(DateTime(timezone=True), default=utcnow)

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(String(64), primary_key=True) # UUID
    timestamp = Column(DateTime(timezone=True), default=utcnow, index=True)
    sender_upi = Column(String(120), index=True, nullable=False)
    sender_name = Column(String(120), default="Simulated Customer")
    recipient_upi = Column(String(120), index=True, nullable=False)
    recipient_name = Column(String(120), default="Recipient")
    amount = Column(Float, nullable=False)
    channel = Column(String(30), default="UPI_P2P") # UPI_P2P, UPI_P2M, QR_CODE, COLLECT_REQUEST
    scenario_type = Column(String(60), default="normal_retail") # ground-truth simulation tag
    
    # Context features
    hour = Column(Integer, nullable=False)
    typical_amount = Column(Float, nullable=False)
    average_amount_30d = Column(Float, nullable=False, default=2500.0)
    transactions_last_24h = Column(Integer, nullable=False, default=1)
    first_merchant_visit = Column(Boolean, nullable=False, default=False)
    payment_service_provider = Column(String(40), nullable=False, default="Unspecified")
    merchant_category = Column(String(60), nullable=False, default="General")
    transaction_state = Column(String(40), nullable=False, default="Unspecified")
    device_os = Column(String(20), nullable=False, default="Unknown")
    transaction_time = Column(Time, nullable=True)
    screening_mode = Column(String(20), nullable=False, default="balanced")
    screening_cutoff = Column(Float, nullable=False, default=0.25)
    # Kept as JSON for compatibility and optional, evolving sandbox metadata.
    input_context = Column(Text, nullable=False, default="{}")
    recent_count_1h = Column(Integer, default=1)
    time_since_last_sec = Column(Float, default=3600.0)
    is_new_recipient = Column(Boolean, default=False)
    device_id = Column(String(64), default="DEV-PRIMARY")
    device_is_new = Column(Boolean, default=False)
    vpn_detected = Column(Boolean, default=False)
    geo_location_flag = Column(String(30), default="normal") # normal, high-risk, unusual
    behavioral_biometric_score = Column(Float, default=0.92) # 0.0 to 1.0 match
    
    # Unified Risk & Decision
    risk_score = Column(Integer, nullable=False) # 0 to 100
    risk_tier = Column(String(20), nullable=False) # LOW, MEDIUM, HIGH, CRITICAL
    decision = Column(String(30), nullable=False) # ALLOW, CHALLENGE, REVIEW, BLOCK
    reasons = Column(Text, default="[]") # JSON list of strings
    
    # Review & Lifecycle
    review_status = Column(String(24), default="CLOSED") # OPEN, UNDER_REVIEW, CLOSED
    reviewer_note = Column(Text, default="")
    assigned_to = Column(String(64), nullable=True)

class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    transaction_id = Column(String(64), ForeignKey("transactions.id"), primary_key=True)
    ml_fraud_probability = Column(Float, nullable=False)
    dl_anomaly_score = Column(Float, nullable=False)
    dl_sequence_score = Column(Float, nullable=False)
    behavioral_score = Column(Float, nullable=False)
    velocity_score = Column(Float, nullable=False)
    device_score = Column(Float, nullable=False)
    beneficiary_score = Column(Float, nullable=False)
    consolidated_risk_score = Column(Integer, nullable=False)
    decision = Column(String(30), nullable=False)
    explanation_json = Column(Text, default="{}")
    calculated_at = Column(DateTime(timezone=True), default=utcnow)

class AgentInvestigation(Base):
    __tablename__ = "agent_investigations"
    id = Column(String(64), primary_key=True) # UUID
    transaction_id = Column(String(64), ForeignKey("transactions.id"), index=True, nullable=False)
    status = Column(String(30), default="INVESTIGATING") # INVESTIGATING, RECOMMENDED_ACTION, CLOSED
    priority = Column(String(20), default="HIGH") # LOW, MEDIUM, HIGH, CRITICAL
    triggered_reason = Column(String(255), nullable=False)
    synthesis_report = Column(Text, default="")
    agent_timeline_json = Column(Text, default="[]")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow)

class User(Base):
    __tablename__ = "users"
    id = Column(String(64), primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=False)
    role = Column(String(24), nullable=False, default="analyst") # admin, analyst, viewer
    created_at = Column(DateTime(timezone=True), default=utcnow)

class CaseAudit(Base):
    __tablename__ = "case_audit"
    id = Column(String(64), primary_key=True)
    transaction_id = Column(String(64), index=True, nullable=False)
    actor_id = Column(String(64), nullable=False)
    action = Column(String(30), nullable=False)
    previous_status = Column(String(24), nullable=False)
    new_status = Column(String(24), nullable=False)
    note = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=utcnow)

class CaseAssignment(Base):
    __tablename__ = "case_assignments"
    transaction_id = Column(String(64), primary_key=True)
    assigned_to = Column(String(64), nullable=False)
    assigned_by = Column(String(64), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow)

class RiskPolicyConfig(Base):
    __tablename__ = "risk_policy_config"
    id = Column(Integer, primary_key=True, default=1)
    weight_ml = Column(Float, default=0.30)
    weight_dl_ae = Column(Float, default=0.20)
    weight_dl_seq = Column(Float, default=0.15)
    weight_behavioral = Column(Float, default=0.15)
    weight_velocity = Column(Float, default=0.10)
    weight_device = Column(Float, default=0.05)
    weight_beneficiary = Column(Float, default=0.05)
    thresh_low = Column(Integer, default=29)
    thresh_medium = Column(Integer, default=59)
    thresh_high = Column(Integer, default=79)
    hard_stop_blacklist = Column(Boolean, default=True)
    hard_stop_daily_limit = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow)

# Indices for high speed querying
Index("idx_tx_time_risk", Transaction.timestamp.desc(), Transaction.risk_tier)
Index("idx_tx_sender_time", Transaction.sender_upi, Transaction.timestamp.desc())
Index("idx_tx_flow_time", Transaction.channel, Transaction.timestamp.desc())
Index("idx_tx_category_time", Transaction.merchant_category, Transaction.timestamp.desc())
Index("idx_tx_state_time", Transaction.transaction_state, Transaction.timestamp.desc())
