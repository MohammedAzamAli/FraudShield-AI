
"""Database models for FraudShield AI.

SQLite is the local development default.
Set DATABASE_URL to use PostgreSQL.
"""

import os
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
    Text,
)
from sqlalchemy.orm import declarative_base, sessionmaker


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./fraudshield.db"
)

engine = create_engine(
    DATABASE_URL,
    connect_args=(
        {"check_same_thread": False}
        if DATABASE_URL.startswith("sqlite")
        else {}
    ),
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


# ============================================================
# TRANSACTION MODEL
# ============================================================

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True)

    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    amount = Column(Float, nullable=False)

    recipient_upi = Column(
        String(100),
        nullable=False,
    )

    typical_amount = Column(Float, nullable=False)
    recent_count = Column(Integer, nullable=False)
    hour = Column(Integer, nullable=False)
    new_recipient = Column(Boolean, nullable=False)

    score = Column(Integer, nullable=False)
    risk = Column(String(16), nullable=False)
    decision = Column(String(32), nullable=False)
    reasons = Column(Text, nullable=False)
    model = Column(String(80), nullable=False)

    review_status = Column(
        String(24),
        nullable=False,
        default="OPEN",
    )

    reviewer_note = Column(
        Text,
        nullable=False,
        default="",
    )


# ============================================================
# USER MODEL
# ============================================================

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)

    email = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    password_hash = Column(
        String(255),
        nullable=False,
    )

    display_name = Column(
        String(100),
        nullable=False,
    )

    role = Column(
        String(24),
        nullable=False,
        default="analyst",
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


# ============================================================
# CASE AUDIT MODEL
# ============================================================

class CaseAudit(Base):
    __tablename__ = "case_audit"

    id = Column(String, primary_key=True)

    transaction_id = Column(
        String,
        index=True,
        nullable=False,
    )

    actor_id = Column(String, nullable=False)
    action = Column(String(30), nullable=False)
    previous_status = Column(String(24), nullable=False)
    new_status = Column(String(24), nullable=False)

    note = Column(
        Text,
        nullable=False,
        default="",
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


# ============================================================
# CASE ASSIGNMENT MODEL
# ============================================================

class CaseAssignment(Base):
    __tablename__ = "case_assignments"

    transaction_id = Column(String, primary_key=True)
    assigned_to = Column(String, nullable=False)
    assigned_by = Column(String, nullable=False)

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


# ============================================================
# v11: PERSISTENT AI INVESTIGATION HISTORY
# ============================================================

class AIInvestigationHistory(Base):
    __tablename__ = "ai_investigation_history"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    actor_id = Column(
        String(255),
        nullable=False,
        index=True,
    )

    transaction_id = Column(
        String(80),
        nullable=True,
        index=True,
    )

    operation = Column(
        String(32),
        nullable=False,
    )

    provider = Column(
        String(32),
        nullable=False,
    )

    model_name = Column(
        String(120),
        nullable=False,
    )

    response_text = Column(
        Text,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
