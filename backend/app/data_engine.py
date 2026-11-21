"""Data Engineering, Customer Behavioral Baselines & Feature Pipeline.
Transforms raw UPI transactions into 20-dimensional engineered feature vectors matching
the production model schema and maintains customer behavioral histories.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
import random
import numpy as np
import pandas as pd

@dataclass
class CustomerProfile:
    id: str
    name: str
    upi_id: str
    account_age_days: int
    daily_spending_limit: float
    typical_amount: float
    typical_hour_start: int
    typical_hour_end: int
    social_trust_score: float
    past_fraud_flags: int
    primary_device_id: str
    home_city: str
    trusted_beneficiaries: List[str] = field(default_factory=list)
    daily_spent_today: float = 0.0
    last_tx_timestamp: Optional[datetime] = None
    tx_count_last_1h: int = 0
    recent_transactions_history: List[dict] = field(default_factory=list)

@dataclass
class BeneficiaryProfile:
    id: str
    upi_id: str
    name: str
    category: str
    verification_status: str # "verified", "recently_registered", "suspicious"
    is_blacklisted: bool
    fraud_complaints_count: int

# In-Memory Realistic Customer Database (simulated banking cohort)
CUSTOMERS: Dict[str, CustomerProfile] = {
    "rahul.sharma@okaxis": CustomerProfile(
        id="CUST-1001", name="Rahul Sharma", upi_id="rahul.sharma@okaxis",
        account_age_days=820, daily_spending_limit=100000.0, typical_amount=2200.0,
        typical_hour_start=8, typical_hour_end=22, social_trust_score=0.92,
        past_fraud_flags=0, primary_device_id="DEV-MUM-9842", home_city="Mumbai",
        trusted_beneficiaries=["grocery.fresh@okhdfc", "utility.power@okicici", "priya.verma@okaxis"]
    ),
    "priya.verma@okaxis": CustomerProfile(
        id="CUST-1002", name="Priya Verma", upi_id="priya.verma@okaxis",
        account_age_days=540, daily_spending_limit=75000.0, typical_amount=1500.0,
        typical_hour_start=9, typical_hour_end=23, social_trust_score=0.88,
        past_fraud_flags=0, primary_device_id="DEV-BLR-4311", home_city="Bengaluru",
        trusted_beneficiaries=["rahul.sharma@okaxis", "coffee.roasters@okicici"]
    ),
    "vikram.singh@okhdfc": CustomerProfile(
        id="CUST-1003", name="Vikram Singh", upi_id="vikram.singh@okhdfc",
        account_age_days=1200, daily_spending_limit=200000.0, typical_amount=8500.0,
        typical_hour_start=7, typical_hour_end=21, social_trust_score=0.95,
        past_fraud_flags=0, primary_device_id="DEV-DEL-7729", home_city="Delhi",
        trusted_beneficiaries=["metro.transit@okaxis", "utility.power@okicici"]
    ),
    "ananya.iyer@okicici": CustomerProfile(
        id="CUST-1004", name="Ananya Iyer", upi_id="ananya.iyer@okicici",
        account_age_days=310, daily_spending_limit=50000.0, typical_amount=1100.0,
        typical_hour_start=10, typical_hour_end=22, social_trust_score=0.82,
        past_fraud_flags=0, primary_device_id="DEV-CHN-1102", home_city="Chennai",
        trusted_beneficiaries=["grocery.fresh@okhdfc"]
    ),
    "arjun.patel@oksbi": CustomerProfile(
        id="CUST-1005", name="Arjun Patel", upi_id="arjun.patel@oksbi",
        account_age_days=95, daily_spending_limit=30000.0, typical_amount=800.0,
        typical_hour_start=9, typical_hour_end=20, social_trust_score=0.65,
        past_fraud_flags=0, primary_device_id="DEV-AHM-5531", home_city="Ahmedabad",
        trusted_beneficiaries=[]
    )
}

BENEFICIARIES: Dict[str, BeneficiaryProfile] = {
    # Legitimate Verified Merchants
    "grocery.fresh@okhdfc": BeneficiaryProfile(
        id="BEN-2001", upi_id="grocery.fresh@okhdfc", name="Fresh Supermarket",
        category="Retail Grocery", verification_status="verified", is_blacklisted=False, fraud_complaints_count=0
    ),
    "coffee.roasters@okicici": BeneficiaryProfile(
        id="BEN-2002", upi_id="coffee.roasters@okicici", name="Artisan Coffee Roasters",
        category="Dining & Cafe", verification_status="verified", is_blacklisted=False, fraud_complaints_count=0
    ),
    "utility.power@okicici": BeneficiaryProfile(
        id="BEN-2003", upi_id="utility.power@okicici", name="State Power Corporation",
        category="Utility Biller", verification_status="verified", is_blacklisted=False, fraud_complaints_count=0
    ),
    "metro.transit@okaxis": BeneficiaryProfile(
        id="BEN-2004", upi_id="metro.transit@okaxis", name="Metropolitan Rail Transit",
        category="Transit Agency", verification_status="verified", is_blacklisted=False, fraud_complaints_count=0
    ),
    # Suspicious / High-Risk / Blacklisted
    "crypto.fastgain@okicici": BeneficiaryProfile(
        id="BEN-9001", upi_id="crypto.fastgain@okicici", name="FastGain Investments",
        category="Unregulated Investment", verification_status="suspicious", is_blacklisted=True, fraud_complaints_count=14
    ),
    "cashback.lottery@paytm": BeneficiaryProfile(
        id="BEN-9002", upi_id="cashback.lottery@paytm", name="Instant Cashback Rewards",
        category="Phishing Collect", verification_status="suspicious", is_blacklisted=True, fraud_complaints_count=23
    ),
    "unknown.mule88@oksbi": BeneficiaryProfile(
        id="BEN-9003", upi_id="unknown.mule88@oksbi", name="Ramesh Kumar (Student)",
        category="Money Mule Account", verification_status="recently_registered", is_blacklisted=False, fraud_complaints_count=4
    ),
    "urgent.transfer@okaxis": BeneficiaryProfile(
        id="BEN-9004", upi_id="urgent.transfer@okaxis", name="Quick Pay Agent",
        category="P2P Suspicious", verification_status="recently_registered", is_blacklisted=False, fraud_complaints_count=2
    )
}

def get_or_create_customer(upi_id: str) -> CustomerProfile:
    if upi_id in CUSTOMERS:
        return CUSTOMERS[upi_id]
    # Dynamically generate synthetic baseline for new customer
    cust = CustomerProfile(
        id=f"CUST-{random.randint(1100, 9999)}",
        name=upi_id.split("@")[0].replace(".", " ").title(),
        upi_id=upi_id,
        account_age_days=random.randint(60, 1000),
        daily_spending_limit=random.choice([50000.0, 100000.0, 150000.0]),
        typical_amount=float(random.randint(1000, 5000)),
        typical_hour_start=8,
        typical_hour_end=22,
        social_trust_score=round(random.uniform(0.70, 0.95), 2),
        past_fraud_flags=0,
        primary_device_id=f"DEV-{random.randint(1000, 9999)}",
        home_city=random.choice(["Mumbai", "Bengaluru", "Delhi", "Hyderabad", "Pune"])
    )
    CUSTOMERS[upi_id] = cust
    return cust

def get_or_create_beneficiary(upi_id: str) -> BeneficiaryProfile:
    if upi_id in BENEFICIARIES:
        return BENEFICIARIES[upi_id]
    is_suspicious = any(w in upi_id.lower() for w in ["crypto", "reward", "cashback", "lottery", "mule", "urgent"])
    ben = BeneficiaryProfile(
        id=f"BEN-{random.randint(3000, 8999)}",
        upi_id=upi_id,
        name=upi_id.split("@")[0].replace(".", " ").title(),
        category="P2P Transfer",
        verification_status="suspicious" if is_suspicious else "recently_registered",
        is_blacklisted=is_suspicious,
        fraud_complaints_count=random.randint(3, 12) if is_suspicious else 0
    )
    BENEFICIARIES[upi_id] = ben
    return ben

def build_feature_vector(
    amount: float,
    customer: CustomerProfile,
    beneficiary: BeneficiaryProfile,
    hour: int,
    recent_count_1h: int,
    time_since_last_sec: float,
    is_new_recipient: bool,
    device_is_new: bool,
    vpn_detected: bool,
    geo_flag: str,
    biometric_score: float
) -> pd.DataFrame:
    """Builds a single-row DataFrame with exact 20 features required by ML/DL pipeline."""
    norm_amount = amount / max(1.0, customer.typical_amount)
    is_high_risk_time = 1 if (hour < 5 or hour > 23) else 0
    is_limit_exceeded = 1 if (customer.daily_spent_today + amount > customer.daily_spending_limit) else 0
    is_recent_high_val = 1 if (amount > 3.0 * customer.typical_amount and recent_count_1h >= 2) else 0
    loc_inconsistent = 1 if geo_flag in ["high-risk", "unusual"] else 0
    
    # Context anomaly composite score
    context_anomalies = 0.0
    if is_high_risk_time: context_anomalies += 0.35
    if vpn_detected: context_anomalies += 0.30
    if device_is_new: context_anomalies += 0.25
    if biometric_score < 0.60: context_anomalies += 0.40
    if norm_amount > 4.0: context_anomalies += 0.45

    row = {
        "Transaction Amount": float(amount),
        "Transaction Frequency": int(recent_count_1h),
        "Recipient Verification Status": str(beneficiary.verification_status),
        "Recipient Blacklist Status": 1 if beneficiary.is_blacklisted else 0,
        "Device Fingerprinting": 1 if not device_is_new else 0,
        "VPN or Proxy Usage": 1 if vpn_detected else 0,
        "Geo-Location Flags": str(geo_flag),
        "Behavioral Biometrics": float(biometric_score),
        "Time Since Last Transaction": float(time_since_last_sec / 60.0), # in minutes
        "Social Trust Score": float(customer.social_trust_score),
        "Account Age": float(customer.account_age_days),
        "High-Risk Transaction Times": int(is_high_risk_time),
        "Past Fraudulent Behavior Flags": int(customer.past_fraud_flags),
        "Location-Inconsistent Transactions": int(loc_inconsistent),
        "Normalized Transaction Amount": float(norm_amount),
        "Transaction Context Anomalies": float(round(context_anomalies, 3)),
        "Fraud Complaints Count": int(beneficiary.fraud_complaints_count),
        "Merchant Category Mismatch": 1 if (beneficiary.category in ["Money Mule Account", "Phishing Collect"] and norm_amount > 2.0) else 0,
        "User Daily Limit Exceeded": int(is_limit_exceeded),
        "Recent High-Value Transaction Flags": int(is_recent_high_val)
    }
    return pd.DataFrame([row])

def build_temporal_sequence_window(customer: CustomerProfile, current_amount: float, current_features: pd.DataFrame) -> np.ndarray:
    """Creates a (1, 5, 5) temporal sequence window for BiGRU evaluation."""
    seq_window = np.zeros((1, 5, 5), dtype=np.float32)
    hist = customer.recent_transactions_history[-4:] # up to 4 past events
    
    # Fill past slots
    for i in range(4):
        if i < len(hist):
            past = hist[i]
            seq_window[0, i] = [
                float(past.get("amount", customer.typical_amount) / max(1.0, customer.typical_amount)),
                float(past.get("time_delta_sec", 1800.0) / 3600.0),
                float(past.get("recent_count", 1)),
                float(past.get("device_risk", 0.05)),
                float(1.0 if past.get("new_recipient", False) else 0.0)
            ]
        else:
            # Baseline normal historical padding
            seq_window[0, i] = [1.0, 2.0, 1.0, 0.05, 0.0]
            
    # Step 4: current transaction
    norm_amt = float(current_features["Normalized Transaction Amount"].iloc[0])
    time_delta_hr = float(current_features["Time Since Last Transaction"].iloc[0]) / 60.0
    freq = float(current_features["Transaction Frequency"].iloc[0])
    dev_risk = 0.90 if (current_features["VPN or Proxy Usage"].iloc[0] == 1 or current_features["Device Fingerprinting"].iloc[0] == 0) else 0.05
    is_new = float(1.0 if current_features["Recipient Verification Status"].iloc[0] != "verified" else 0.0)
    
    seq_window[0, 4] = [norm_amt, time_delta_hr, freq, dev_risk, is_new]
    return seq_window
