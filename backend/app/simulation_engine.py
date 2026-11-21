"""Autonomous Real-Time Transaction Generator & Event Stream Dispatcher.
Generates realistic financial streams, runs complete ML/DL/Risk scoring in real-time,
triggers multi-agent investigations, and broadcasts live events over WebSockets.
"""
import asyncio
import json
import random
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from uuid import uuid4

from .db import SessionLocal, Transaction, RiskAssessment, AgentInvestigation
from .data_engine import (
    CUSTOMERS, BENEFICIARIES, get_or_create_customer, get_or_create_beneficiary,
    build_feature_vector, build_temporal_sequence_window
)
from .ml_engine import get_ml_engine
from .risk_engine import evaluate_transaction_risk, DEFAULT_CONFIG
from .agent_swarm import get_investigation_orchestrator

class RealTimeSimulationEngine:
    def __init__(self):
        self.state: str = "STOPPED" # RUNNING, PAUSED, STOPPED
        self.interval_sec: float = 2.0
        self.scenario_mode: str = "MIXED" # MIXED, NORMAL, VELOCITY, ATO, MULE, PHISHING
        self.active_task: Optional[asyncio.Task] = None
        self.websocket_subscribers: List[Any] = []
        self.transactions_generated_count: int = 0
        self.lock = asyncio.Lock()

    def get_status(self) -> dict:
        return {
            "state": self.state,
            "interval_sec": self.interval_sec,
            "scenario_mode": self.scenario_mode,
            "total_generated": self.transactions_generated_count,
            "connected_clients": len(self.websocket_subscribers)
        }

    async def register_websocket(self, ws):
        self.websocket_subscribers.append(ws)

    def unregister_websocket(self, ws):
        if ws in self.websocket_subscribers:
            self.websocket_subscribers.remove(ws)

    async def broadcast_event(self, event_type: str, data: dict):
        dead_clients = []
        payload = {"event": event_type, "data": data, "timestamp": datetime.now(timezone.utc).isoformat()}
        for ws in self.websocket_subscribers:
            try:
                await ws.send_json(payload)
            except Exception:
                dead_clients.append(ws)
        for dead in dead_clients:
            self.unregister_websocket(dead)

    def generate_single_event(self, scenario_override: Optional[str] = None) -> dict:
        """Constructs and processes a realistic simulated transaction."""
        scenario = scenario_override or self.scenario_mode
        if scenario == "MIXED":
            r = random.random()
            if r < 0.70: scenario = "NORMAL"
            elif r < 0.80: scenario = "VELOCITY"
            elif r < 0.90: scenario = "ATO"
            elif r < 0.95: scenario = "MULE"
            else: scenario = "PHISHING"

        # Select customer
        sender_keys = list(CUSTOMERS.keys())
        sender_id = random.choice(sender_keys)
        customer = CUSTOMERS[sender_id]
        
        now = datetime.now(timezone.utc)
        hour = now.hour
        tx_id = str(uuid4())
        
        # Scenario configurations
        if scenario == "NORMAL":
            ben_id = random.choice(["grocery.fresh@okhdfc", "coffee.roasters@okicici", "utility.power@okicici", "metro.transit@okaxis"])
            beneficiary = BENEFICIARIES[ben_id]
            amount = round(random.uniform(150.0, customer.typical_amount * 1.2), 2)
            recent_count = random.randint(1, 3)
            time_since_sec = random.uniform(1800, 14400)
            device_new = False
            vpn = False
            geo_flag = "normal"
            biometric = round(random.uniform(0.85, 0.98), 2)
            channel = "UPI_P2M" if "merchant" in beneficiary.category.lower() or "retail" in beneficiary.category.lower() else "UPI_P2P"
            is_new_recipient = beneficiary.upi_id not in customer.trusted_beneficiaries
            tag = "normal_retail"
            
        elif scenario == "VELOCITY":
            ben_id = random.choice(["urgent.transfer@okaxis", "unknown.mule88@oksbi", "crypto.fastgain@okicici"])
            beneficiary = BENEFICIARIES[ben_id]
            amount = round(random.uniform(customer.typical_amount * 1.5, customer.typical_amount * 3.5), 2)
            recent_count = random.randint(7, 14)
            time_since_sec = random.uniform(15, 60)
            device_new = random.choice([True, False])
            vpn = random.choice([True, False])
            geo_flag = "unusual"
            biometric = round(random.uniform(0.60, 0.75), 2)
            channel = "UPI_P2P"
            is_new_recipient = True
            tag = "velocity_burst"

        elif scenario == "ATO": # Account Takeover
            ben_id = "crypto.fastgain@okicici"
            beneficiary = BENEFICIARIES[ben_id]
            amount = round(random.uniform(customer.typical_amount * 6.0, customer.typical_amount * 12.0), 2)
            recent_count = random.randint(2, 5)
            time_since_sec = random.uniform(300, 1200)
            device_new = True
            vpn = True
            geo_flag = "high-risk"
            biometric = round(random.uniform(0.20, 0.45), 2) # severe cadence mismatch
            hour = 3 # uncharacteristic overnight timing
            channel = "UPI_P2P"
            is_new_recipient = True
            tag = "account_takeover"

        elif scenario == "MULE": # Money Mule Funnel
            ben_id = "unknown.mule88@oksbi"
            beneficiary = BENEFICIARIES[ben_id]
            amount = round(random.uniform(15000.0, 48000.0), 2)
            recent_count = random.randint(4, 8)
            time_since_sec = random.uniform(60, 240)
            device_new = False
            vpn = False
            geo_flag = "normal"
            biometric = round(random.uniform(0.70, 0.85), 2)
            channel = "UPI_P2P"
            is_new_recipient = True
            tag = "mule_funnel"

        else: # PHISHING Collect Request
            ben_id = "cashback.lottery@paytm"
            beneficiary = BENEFICIARIES[ben_id]
            amount = round(random.uniform(25000.0, 60000.0), 2)
            recent_count = 1
            time_since_sec = 7200.0
            device_new = False
            vpn = True
            geo_flag = "unusual"
            biometric = round(random.uniform(0.40, 0.65), 2)
            channel = "COLLECT_REQUEST"
            is_new_recipient = True
            tag = "phishing_collect_request"

        # Build 20 Features
        features_df = build_feature_vector(
            amount=amount,
            customer=customer,
            beneficiary=beneficiary,
            hour=hour,
            recent_count_1h=recent_count,
            time_since_last_sec=time_since_sec,
            is_new_recipient=is_new_recipient,
            device_is_new=device_new,
            vpn_detected=vpn,
            geo_flag=geo_flag,
            biometric_score=biometric
        )
        
        # Build 5-step sequence window
        seq_window = build_temporal_sequence_window(customer, amount, features_df)
        
        # ML & DL Inference
        ml_engine = get_ml_engine()
        ml_res = ml_engine.predict_ml(features_df)
        dl_ae_res = ml_engine.predict_dl_anomaly(features_df)
        dl_seq_res = ml_engine.predict_dl_sequence(seq_window)
        
        # Multi-Tier Risk Evaluation
        risk_res = evaluate_transaction_risk(
            features=features_df,
            customer=customer,
            beneficiary=beneficiary,
            ml_output=ml_res,
            dl_ae_output=dl_ae_res,
            dl_seq_output=dl_seq_res
        )
        
        # Update customer state
        customer.daily_spent_today += amount
        customer.last_tx_timestamp = now
        customer.recent_transactions_history.append({
            "amount": amount,
            "time_delta_sec": time_since_sec,
            "recent_count": recent_count,
            "device_risk": 0.90 if vpn or device_new else 0.05,
            "new_recipient": is_new_recipient
        })
        if len(customer.recent_transactions_history) > 20:
            customer.recent_transactions_history.pop(0)

        tx_record = {
            "id": tx_id,
            "timestamp": now.isoformat(),
            "sender_upi": customer.upi_id,
            "sender_name": customer.name,
            "recipient_upi": beneficiary.upi_id,
            "recipient_name": beneficiary.name,
            "amount": amount,
            "channel": channel,
            "scenario_type": tag,
            "hour": hour,
            "typical_amount": customer.typical_amount,
            "recent_count_1h": recent_count,
            "time_since_last_sec": round(time_since_sec, 1),
            "is_new_recipient": is_new_recipient,
            "device_id": f"DEV-{random.randint(1000, 9999)}" if device_new else customer.primary_device_id,
            "device_is_new": device_new,
            "vpn_detected": vpn,
            "geo_location_flag": geo_flag,
            "behavioral_biometric_score": biometric,
            "risk_score": risk_res["consolidated_risk_score"],
            "risk_tier": risk_res["risk_tier"],
            "decision": risk_res["decision"],
            "reasons": risk_res["reasons"],
            "review_status": "OPEN" if risk_res["risk_tier"] in ["HIGH", "CRITICAL"] else "CLOSED",
            "reviewer_note": "",
            "assigned_to": None,
            "score": risk_res["consolidated_risk_score"], # backward compatibility
            "risk": risk_res["risk_tier"],              # backward compatibility
            "model": "production-ensemble-v1"
        }

        # Run Multi-Agent Investigation if High or Critical risk
        agent_investigation_result = None
        if risk_res["risk_tier"] in ["HIGH", "CRITICAL"]:
            orchestrator = get_investigation_orchestrator()
            agent_investigation_result = orchestrator.run_investigation(
                tx_data=tx_record,
                risk_result=risk_res,
                customer=customer,
                beneficiary=beneficiary
            )

        # Persist to Database
        db = SessionLocal()
        try:
            db_tx = Transaction(
                id=tx_id,
                timestamp=now,
                sender_upi=customer.upi_id,
                sender_name=customer.name,
                recipient_upi=beneficiary.upi_id,
                recipient_name=beneficiary.name,
                amount=amount,
                channel=channel,
                scenario_type=tag,
                hour=hour,
                typical_amount=customer.typical_amount,
                recent_count_1h=recent_count,
                time_since_last_sec=time_since_sec,
                is_new_recipient=is_new_recipient,
                device_id=tx_record["device_id"],
                device_is_new=device_new,
                vpn_detected=vpn,
                geo_location_flag=geo_flag,
                behavioral_biometric_score=biometric,
                risk_score=risk_res["consolidated_risk_score"],
                risk_tier=risk_res["risk_tier"],
                decision=risk_res["decision"],
                reasons=json.dumps(risk_res["reasons"]),
                review_status=tx_record["review_status"]
            )
            db.add(db_tx)
            
            db_risk = RiskAssessment(
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
            db.add(db_risk)
            
            if agent_investigation_result:
                db_inv = AgentInvestigation(
                    id=agent_investigation_result["case_id"],
                    transaction_id=tx_id,
                    status="INVESTIGATING" if risk_res["risk_tier"] == "HIGH" else "RECOMMENDED_ACTION",
                    priority=risk_res["risk_tier"],
                    triggered_reason="; ".join(risk_res["reasons"][:2]),
                    synthesis_report=agent_investigation_result["dossier_summary"],
                    agent_timeline_json=json.dumps(agent_investigation_result["timeline"])
                )
                db.add(db_inv)
                
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Error persisting simulated transaction: {e}")
        finally:
            db.close()

        self.transactions_generated_count += 1
        
        return {
            "transaction": tx_record,
            "risk_assessment": risk_res,
            "agent_investigation": agent_investigation_result
        }

    async def _simulation_loop(self):
        while self.state == "RUNNING":
            try:
                event = self.generate_single_event()
                await self.broadcast_event("transaction", event["transaction"])
                if event["agent_investigation"]:
                    await self.broadcast_event("agent_investigation", event["agent_investigation"])
                await asyncio.sleep(self.interval_sec)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Simulation loop error: {e}")
                await asyncio.sleep(self.interval_sec)

    async def start(self, interval_sec: float = 2.0, scenario_mode: str = "MIXED"):
        async with self.lock:
            self.interval_sec = interval_sec
            self.scenario_mode = scenario_mode
            if self.state != "RUNNING":
                self.state = "RUNNING"
                self.active_task = asyncio.create_task(self._simulation_loop())

    async def pause(self):
        async with self.lock:
            if self.state == "RUNNING":
                self.state = "PAUSED"
                if self.active_task:
                    self.active_task.cancel()
                    self.active_task = None

    async def resume(self):
        async with self.lock:
            if self.state == "PAUSED":
                self.state = "RUNNING"
                self.active_task = asyncio.create_task(self._simulation_loop())

    async def stop(self):
        async with self.lock:
            self.state = "STOPPED"
            if self.active_task:
                self.active_task.cancel()
                self.active_task = None

_simulation_engine = None

def get_simulation_engine() -> RealTimeSimulationEngine:
    global _simulation_engine
    if _simulation_engine is None:
        _simulation_engine = RealTimeSimulationEngine()
    return _simulation_engine
