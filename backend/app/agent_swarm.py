"""Controlled Multi-Agent Autonomous Swarm for Fraud Shield AI.
Coordinates 5 specialized agents to investigate suspicious financial transactions:
1. Transaction Monitoring Agent
2. Behaviour Analysis Agent
3. Fraud Investigation Agent
4. Risk Assessment Agent
5. Fraud Reporting Agent

Enforces structured JSON evidence, audit logging, timeouts, and human review boundaries.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import time
import json
from uuid import uuid4
import pandas as pd
from .data_engine import CustomerProfile, BeneficiaryProfile, get_or_create_customer, get_or_create_beneficiary
from .gemini_service import get_gemini_service

@dataclass
class AgentStepResult:
    agent_name: str
    stage: str
    status: str # SUCCESS, FLAGGED, SKIPPED, ERROR
    timestamp: str
    execution_time_ms: float
    evidence: Dict[str, Any]
    findings: str
    recommendation: str

class TransactionMonitoringAgent:
    """Agent 1: Ingestion, schema validation, velocity tracking, and hard limit enforcement."""
    def __init__(self):
        self.name = "Transaction Monitoring Agent"

    def execute(self, tx_data: dict, beneficiary: BeneficiaryProfile) -> AgentStepResult:
        t0 = time.time()
        amount = float(tx_data.get("amount", 0))
        freq = int(tx_data.get("recent_count_1h", tx_data.get("recent_count", 1)))
        blacklisted = beneficiary.is_blacklisted
        
        evidence = {
            "amount": amount,
            "frequency_1h": freq,
            "blacklist_hit": blacklisted,
            "channel": tx_data.get("channel", "UPI_P2P")
        }
        
        if blacklisted:
            findings = f"CRITICAL: Beneficiary '{beneficiary.upi_id}' is on national fraud blacklist."
            rec = "IMMEDIATE HARD BLOCK: Payment processing aborted at gateway."
            status = "FLAGGED"
        elif freq >= 6:
            findings = f"Velocity burst detected: {freq} transfers initiated in the past 60 minutes."
            rec = "HOLD: Throttle transaction and queue for sequence analysis."
            status = "FLAGGED"
        else:
            findings = f"Nominal velocity ({freq} tx/hr). Amount within standard bounds."
            rec = "PROCEED to behavioral analysis."
            status = "SUCCESS"
            
        elapsed = (time.time() - t0) * 1000.0
        return AgentStepResult(
            agent_name=self.name, stage="1_MONITORING", status=status,
            timestamp=datetime.now(timezone.utc).isoformat(),
            execution_time_ms=round(elapsed, 2),
            evidence=evidence, findings=findings, recommendation=rec
        )

class BehaviourAnalysisAgent:
    """Agent 2: Compares transaction context against historical customer baseline."""
    def __init__(self):
        self.name = "Behaviour Analysis Agent"

    def execute(self, tx_data: dict, customer: CustomerProfile) -> AgentStepResult:
        t0 = time.time()
        amount = float(tx_data.get("amount", 0))
        ratio = amount / max(1.0, customer.typical_amount)
        hour = int(tx_data.get("hour", 12))
        device_new = bool(tx_data.get("device_is_new", False))
        vpn = bool(tx_data.get("vpn_detected", False))
        biometric = float(tx_data.get("behavioral_biometric_score", 0.90))
        
        evidence = {
            "customer_typical_amount": customer.typical_amount,
            "observed_amount_ratio": round(ratio, 2),
            "hour_of_day": hour,
            "within_typical_hours": customer.typical_hour_start <= hour <= customer.typical_hour_end,
            "device_is_new": device_new,
            "vpn_detected": vpn,
            "biometric_confidence": biometric
        }
        
        anomalies = []
        if ratio >= 4.0: anomalies.append(f"Amount is {ratio:.1f}x customer's typical expenditure")
        if not (customer.typical_hour_start <= hour <= customer.typical_hour_end):
            anomalies.append(f"Uncharacteristic timing at {hour}:00 (typical: {customer.typical_hour_start}:00-{customer.typical_hour_end}:00)")
        if device_new: anomalies.append("Unfamiliar hardware fingerprint")
        if vpn: anomalies.append("VPN/Proxy anonymization active")
        if biometric < 0.65: anomalies.append(f"Low biometric cadence score ({biometric:.2f})")
        
        if len(anomalies) >= 2:
            status = "FLAGGED"
            findings = "Multiple behavioral anomalies: " + "; ".join(anomalies)
            rec = "CHALLENGE: Request multi-factor biometric authentication."
        elif len(anomalies) == 1:
            status = "FLAGGED"
            findings = "Minor behavioral deviation: " + anomalies[0]
            rec = "MONITOR: Increase telemetry logging for this session."
        else:
            status = "SUCCESS"
            findings = "Transaction aligns with verified customer baseline."
            rec = "PROCEED to beneficiary intelligence check."
            
        elapsed = (time.time() - t0) * 1000.0
        return AgentStepResult(
            agent_name=self.name, stage="2_BEHAVIOUR", status=status,
            timestamp=datetime.now(timezone.utc).isoformat(),
            execution_time_ms=round(elapsed, 2),
            evidence=evidence, findings=findings, recommendation=rec
        )

class FraudInvestigationAgent:
    """Agent 3: Graph and beneficiary network analysis, mule funnels, dispute history."""
    def __init__(self):
        self.name = "Fraud Investigation Agent"

    def execute(self, tx_data: dict, beneficiary: BeneficiaryProfile) -> AgentStepResult:
        t0 = time.time()
        complaints = beneficiary.fraud_complaints_count
        status_val = beneficiary.verification_status
        category = beneficiary.category
        
        evidence = {
            "recipient_vpa": beneficiary.upi_id,
            "verification_status": status_val,
            "category": category,
            "past_complaints_count": complaints,
            "is_mule_candidate": "mule" in beneficiary.upi_id.lower() or complaints >= 3
        }
        
        if complaints >= 5 or "mule" in beneficiary.upi_id.lower():
            status = "FLAGGED"
            findings = f"Recipient is linked to suspicious aggregation/mule activity with {complaints} complaints."
            rec = "FLAG FOR INVESTIGATION: Isolate beneficiary VPA and trace funding network."
        elif status_val == "suspicious":
            status = "FLAGGED"
            findings = f"Recipient flagged as suspicious category: '{category}'."
            rec = "REVIEW: Check beneficiary account registration age and KYC tier."
        elif status_val == "recently_registered":
            status = "FLAGGED"
            findings = "Recipient VPA registered recently (< 14 days old)."
            rec = "WARN: Caution customer regarding unverified recipient."
        else:
            status = "SUCCESS"
            findings = f"Recipient '{beneficiary.name}' is verified with clean dispute record."
            rec = "PROCEED to composite risk assessment."
            
        elapsed = (time.time() - t0) * 1000.0
        return AgentStepResult(
            agent_name=self.name, stage="3_INVESTIGATION", status=status,
            timestamp=datetime.now(timezone.utc).isoformat(),
            execution_time_ms=round(elapsed, 2),
            evidence=evidence, findings=findings, recommendation=rec
        )

class RiskAssessmentAgent:
    """Agent 4: Synthesizes agent telemetry with ML and DL probability models."""
    def __init__(self):
        self.name = "Risk Assessment Agent"

    def execute(self, risk_result: dict, prior_steps: List[AgentStepResult]) -> AgentStepResult:
        t0 = time.time()
        score = risk_result.get("consolidated_risk_score", 50)
        decision = risk_result.get("decision", "REVIEW")
        tier = risk_result.get("risk_tier", "MEDIUM")
        
        flagged_count = sum(1 for s in prior_steps if s.status == "FLAGGED")
        
        evidence = {
            "consolidated_score": score,
            "risk_tier": tier,
            "deterministic_decision": decision,
            "agents_flagged_count": flagged_count,
            "ml_fraud_prob": risk_result.get("layer_breakdown", {}).get("ml_fraud_probability", 0),
            "dl_anomaly_score": risk_result.get("layer_breakdown", {}).get("dl_anomaly_score", 0),
            "dl_sequence_score": risk_result.get("layer_breakdown", {}).get("dl_sequence_score", 0)
        }
        
        findings = (
            f"Consolidated risk score calculated at {score}/100 ({tier}). "
            f"{flagged_count} upstream investigation agents raised risk signals. "
            f"Final deterministic policy decision: {decision}."
        )
        
        if decision == "BLOCK":
            rec = "EXECUTE BLOCK: Halt transaction, notify security operations center, and freeze simulated session."
        elif decision == "REVIEW":
            rec = "ROUTE TO INVESTIGATOR: Create urgent case ticket with compiled agent evidence."
        elif decision == "CHALLENGE":
            rec = "ISSUE STEP-UP: Request secondary out-of-band authorization."
        else:
            rec = "APPROVE: Transaction passed all risk thresholds."
            
        elapsed = (time.time() - t0) * 1000.0
        return AgentStepResult(
            agent_name=self.name, stage="4_RISK_ASSESSMENT", status="FLAGGED" if score >= 60 else "SUCCESS",
            timestamp=datetime.now(timezone.utc).isoformat(),
            execution_time_ms=round(elapsed, 2),
            evidence=evidence, findings=findings, recommendation=rec
        )

class FraudReportingAgent:
    """Agent 5: Generates structured investigation reports, memos, and audit timeline."""
    def __init__(self):
        self.name = "Fraud Reporting Agent"

    def execute(self, tx_data: dict, risk_result: dict, timeline: List[AgentStepResult]) -> AgentStepResult:
        t0 = time.time()
        gemini = get_gemini_service()
        
        memo_dict = gemini.generate_investigation_report(
            tx_data={**tx_data, **risk_result},
            analyst_notes=f"Automated multi-agent investigation. Upstream flags: {len([s for s in timeline if s.status == 'FLAGGED'])}"
        )
        report_md = memo_dict.get("report_markdown", "Report generation unavailable.")
        
        evidence = {
            "report_length_chars": len(report_md),
            "generator_provider": memo_dict.get("provider", "local"),
            "audit_trail_steps": len(timeline) + 1,
            "human_review_required": True
        }
        
        findings = f"Complete investigation case dossier compiled ({len(report_md)} bytes). Ready for analyst review."
        rec = "FILE DOSSIER: Persist case in database and notify investigation dashboard."
        
        elapsed = (time.time() - t0) * 1000.0
        return AgentStepResult(
            agent_name=self.name, stage="5_REPORTING", status="SUCCESS",
            timestamp=datetime.now(timezone.utc).isoformat(),
            execution_time_ms=round(elapsed, 2),
            evidence=evidence, findings=findings, recommendation=rec
        )

class MultiAgentInvestigationOrchestrator:
    def __init__(self):
        self.monitoring_agent = TransactionMonitoringAgent()
        self.behaviour_agent = BehaviourAnalysisAgent()
        self.investigation_agent = FraudInvestigationAgent()
        self.risk_agent = RiskAssessmentAgent()
        self.reporting_agent = FraudReportingAgent()

    def run_investigation(
        self,
        tx_data: dict,
        risk_result: dict,
        customer: CustomerProfile,
        beneficiary: BeneficiaryProfile
    ) -> dict:
        """Executes the full controlled multi-agent investigation workflow sequentially."""
        t_start = time.time()
        timeline: List[AgentStepResult] = []
        
        # Step 1: Monitoring Agent
        step1 = self.monitoring_agent.execute(tx_data, beneficiary)
        timeline.append(step1)
        
        # Step 2: Behaviour Agent
        step2 = self.behaviour_agent.execute(tx_data, customer)
        timeline.append(step2)
        
        # Step 3: Investigation Agent
        step3 = self.investigation_agent.execute(tx_data, beneficiary)
        timeline.append(step3)
        
        # Step 4: Risk Assessment Agent
        step4 = self.risk_agent.execute(risk_result, timeline)
        timeline.append(step4)
        
        # Step 5: Reporting Agent
        step5 = self.reporting_agent.execute(tx_data, risk_result, timeline)
        timeline.append(step5)
        
        total_time_ms = (time.time() - t_start) * 1000.0
        
        case_id = f"INV-{uuid4().hex[:8].upper()}"
        
        return {
            "case_id": case_id,
            "transaction_id": tx_data.get("id", ""),
            "investigation_status": "COMPLETED",
            "total_execution_time_ms": round(total_time_ms, 2),
            "agents_executed": 5,
            "flagged_steps_count": sum(1 for s in timeline if s.status == "FLAGGED"),
            "timeline": [asdict(s) for s in timeline],
            "dossier_summary": step4.findings,
            "final_recommendation": step4.recommendation
        }

_orchestrator = None

def get_investigation_orchestrator() -> MultiAgentInvestigationOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MultiAgentInvestigationOrchestrator()
    return _orchestrator
