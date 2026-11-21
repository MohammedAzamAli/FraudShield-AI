"""Centralized Multi-Tier Risk Scoring and Deterministic Policy Engine.
Combines:
1. Production ML Ensemble Probability (0-100)
2. PyTorch Deep Anomaly Autoencoder Score (0-100)
3. PyTorch Deep Behavioral Sequence BiGRU Score (0-100)
4. Customer Behavioral Deviation Score (0-100)
5. Transaction Velocity Indicators (0-100)
6. Device & Network Fingerprint Risk (0-100)
7. Beneficiary Trust & Blacklist Signals (0-100)

Produces:
- Consolidated Risk Score (0-100)
- Deterministic Decision: ALLOW (0-29), CHALLENGE (30-59), REVIEW (60-79), BLOCK (80-100)
- Hard Stop Overrides (Blacklist, Daily Limit Exhaustion, Phishing Signature)
"""
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any
import pandas as pd
from .data_engine import CustomerProfile, BeneficiaryProfile

@dataclass
class RiskEngineConfig:
    # Layer weights summing to 1.0
    weight_ml: float = 0.30
    weight_dl_ae: float = 0.20
    weight_dl_seq: float = 0.15
    weight_behavioral: float = 0.15
    weight_velocity: float = 0.10
    weight_device: float = 0.05
    weight_beneficiary: float = 0.05
    
    # Configurable decision boundaries
    thresh_low: int = 29      # 0..29 -> ALLOW
    thresh_medium: int = 59   # 30..59 -> CHALLENGE
    thresh_high: int = 79     # 60..79 -> REVIEW
                              # 80..100 -> BLOCK
    
    hard_stop_blacklist: bool = True
    hard_stop_daily_limit: bool = True

DEFAULT_CONFIG = RiskEngineConfig()

def compute_behavioral_score(features: pd.DataFrame, customer: CustomerProfile) -> Tuple[float, List[str]]:
    score = 0.0
    reasons = []
    norm_amt = float(features["Normalized Transaction Amount"].iloc[0])
    high_risk_time = int(features["High-Risk Transaction Times"].iloc[0])
    limit_exceeded = int(features["User Daily Limit Exceeded"].iloc[0])
    
    if norm_amt >= 5.0:
        score += 55.0
        reasons.append(f"Transaction amount is {norm_amt:.1f}x higher than customer typical spend (₹{customer.typical_amount:,.0f})")
    elif norm_amt >= 2.5:
        score += 30.0
        reasons.append(f"Transaction amount is {norm_amt:.1f}x higher than normal baseline")
        
    if high_risk_time:
        score += 25.0
        reasons.append("Payment initiated during abnormal overnight hours (outside typical 08:00-22:00 window)")
        
    if limit_exceeded:
        score += 40.0
        reasons.append(f"Payment exceeds customer's daily limit of ₹{customer.daily_spending_limit:,.0f}")
        
    return min(100.0, score), reasons

def compute_velocity_score(features: pd.DataFrame) -> Tuple[float, List[str]]:
    score = 0.0
    reasons = []
    freq = int(features["Transaction Frequency"].iloc[0])
    time_since_min = float(features["Time Since Last Transaction"].iloc[0])
    
    if freq >= 6 or time_since_min < 1.0:
        score += 85.0
        reasons.append(f"Rapid velocity burst: {freq} transfers in the last hour ({time_since_min:.1f} min since previous)")
    elif freq >= 3 or time_since_min < 5.0:
        score += 45.0
        reasons.append(f"Elevated transaction velocity: {freq} transfers in the last hour")
        
    return min(100.0, score), reasons

def compute_device_score(features: pd.DataFrame) -> Tuple[float, List[str]]:
    score = 0.0
    reasons = []
    vpn = int(features["VPN or Proxy Usage"].iloc[0])
    new_dev = 1 if features["Device Fingerprinting"].iloc[0] == 0 else 0
    bio = float(features["Behavioral Biometrics"].iloc[0])
    geo_flag = str(features["Geo-Location Flags"].iloc[0])
    
    if vpn:
        score += 35.0
        reasons.append("VPN / Anonymizing Proxy detected on active session")
    if new_dev:
        score += 25.0
        reasons.append("Unfamiliar hardware fingerprint; first time transaction from this device")
    if bio < 0.60:
        score += 35.0
        reasons.append(f"Behavioral biometric mismatch: cadence confidence is low ({bio:.2f})")
    if geo_flag in ["high-risk", "unusual"]:
        score += 25.0
        reasons.append(f"Inconsistent geolocation telemetry: flagged as '{geo_flag}'")
        
    return min(100.0, score), reasons

def compute_beneficiary_score(features: pd.DataFrame, beneficiary: BeneficiaryProfile) -> Tuple[float, List[str]]:
    score = 0.0
    reasons = []
    blacklisted = int(features["Recipient Blacklist Status"].iloc[0])
    status = str(features["Recipient Verification Status"].iloc[0])
    complaints = int(features["Fraud Complaints Count"].iloc[0])
    
    if blacklisted:
        score += 100.0
        reasons.append(f"CRITICAL: Recipient VPA ({beneficiary.upi_id}) is listed on the national fraud blacklist")
    elif status == "suspicious":
        score += 65.0
        reasons.append("Recipient flagged as suspicious by intelligence network")
    elif status == "recently_registered":
        score += 25.0
        reasons.append("Recipient VPA was created recently (< 14 days old)")
        
    if complaints > 0:
        score += min(40.0, complaints * 8.0)
        reasons.append(f"Recipient has {complaints} recorded customer fraud dispute(s)")
        
    return min(100.0, score), reasons

def evaluate_transaction_risk(
    features: pd.DataFrame,
    customer: CustomerProfile,
    beneficiary: BeneficiaryProfile,
    ml_output: dict,
    dl_ae_output: dict,
    dl_seq_output: dict,
    config: RiskEngineConfig = DEFAULT_CONFIG
) -> dict:
    """Consolidates all layers into a final 0-100 risk score and deterministic decision."""
    ml_prob = ml_output.get("ensemble_fraud_probability", 0.0)
    dl_ae_prob = dl_ae_output.get("dl_anomaly_score", 0.0)
    dl_seq_prob = dl_seq_output.get("dl_sequence_risk_score", 0.0)
    
    ml_scaled = ml_prob * 100.0
    dl_ae_scaled = dl_ae_prob * 100.0
    dl_seq_scaled = dl_seq_prob * 100.0
    
    beh_score, beh_reasons = compute_behavioral_score(features, customer)
    vel_score, vel_reasons = compute_velocity_score(features)
    dev_score, dev_reasons = compute_device_score(features)
    ben_score, ben_reasons = compute_beneficiary_score(features, beneficiary)
    
    # Consolidated Weighted Score
    raw_composite = (
        ml_scaled * config.weight_ml +
        dl_ae_scaled * config.weight_dl_ae +
        dl_seq_scaled * config.weight_dl_seq +
        beh_score * config.weight_behavioral +
        vel_score * config.weight_velocity +
        dev_score * config.weight_device +
        ben_score * config.weight_beneficiary
    )
    
    composite_score = int(round(raw_composite))
    composite_score = max(0, min(100, composite_score))
    
    all_reasons = []
    all_reasons.extend(ben_reasons)
    all_reasons.extend(beh_reasons)
    all_reasons.extend(vel_reasons)
    all_reasons.extend(dev_reasons)
    
    if ml_output.get("flagged", False):
        all_reasons.append(f"Production ML Ensemble flagged high fraud probability ({ml_prob*100:.1f}%)")
    if dl_ae_output.get("flagged", False):
        all_reasons.append(f"Deep Autoencoder detected latent transaction anomaly ({dl_ae_prob*100:.1f}%)")
    if dl_seq_output.get("flagged", False):
        all_reasons.append(f"Deep Behavioral BiGRU detected suspicious sequence pattern ({dl_seq_prob*100:.1f}%)")
        
    # Hard Overrides
    hard_override_triggered = False
    if config.hard_stop_blacklist and beneficiary.is_blacklisted:
        composite_score = max(composite_score, 95)
        decision = "BLOCK"
        hard_override_triggered = True
    elif config.hard_stop_daily_limit and features["User Daily Limit Exceeded"].iloc[0] == 1 and composite_score >= 60:
        composite_score = max(composite_score, 85)
        decision = "BLOCK"
        hard_override_triggered = True
    else:
        # Standard Decision Boundaries
        if composite_score <= config.thresh_low:
            risk_tier = "LOW"
            decision = "ALLOW"
        elif composite_score <= config.thresh_medium:
            risk_tier = "MEDIUM"
            decision = "CHALLENGE"
        elif composite_score <= config.thresh_high:
            risk_tier = "HIGH"
            decision = "REVIEW"
        else:
            risk_tier = "CRITICAL"
            decision = "BLOCK"
            
    # Set final risk tier from score
    if composite_score >= 80:
        risk_tier = "CRITICAL"
    elif composite_score >= 60:
        risk_tier = "HIGH"
    elif composite_score >= 30:
        risk_tier = "MEDIUM"
    else:
        risk_tier = "LOW"
        
    return {
        "consolidated_risk_score": composite_score,
        "risk_tier": risk_tier,
        "decision": decision,
        "hard_override_triggered": hard_override_triggered,
        "reasons": all_reasons,
        "layer_breakdown": {
            "ml_fraud_probability": round(ml_prob, 4),
            "dl_anomaly_score": round(dl_ae_prob, 4),
            "dl_sequence_score": round(dl_seq_prob, 4),
            "behavioral_score": round(beh_score, 1),
            "velocity_score": round(vel_score, 1),
            "device_score": round(dev_score, 1),
            "beneficiary_score": round(ben_score, 1)
        },
        "weights_applied": {
            "ml": config.weight_ml,
            "dl_ae": config.weight_dl_ae,
            "dl_seq": config.weight_dl_seq,
            "behavioral": config.weight_behavioral,
            "velocity": config.weight_velocity,
            "device": config.weight_device,
            "beneficiary": config.weight_beneficiary
        }
    }
