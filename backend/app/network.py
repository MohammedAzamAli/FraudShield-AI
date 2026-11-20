"""Synthetic Fraud Network Explorer API.
Provides deterministic scenarios for normal activity, mule funnel aggregation,
and rapid pass-through payments. All records are explicitly synthetic demonstration data.
"""
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select
from .db import Transaction, CaseAudit, CaseAssignment, SessionLocal

router = APIRouter(prefix="/api/network", tags=["Synthetic Network Explorer"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Base timestamp for deterministic scenarios (fixed reference point for academic repeatability)
SCENARIO_BASE_TIME = datetime(2026, 11, 20, 2, 0, 0, tzinfo=timezone.utc)

def build_scenarios() -> Dict[str, Dict[str, Any]]:
    """Builds deterministic synthetic scenarios for network exploration."""
    t0 = SCENARIO_BASE_TIME

    # 1. NORMAL ACTIVITY SCENARIO
    normal_nodes = [
        {"id": "alice.sharma@okaxis", "label": "Alice Sharma", "role": "normal", "type": "Payer", "inflow": 1200.0, "outflow": 2950.0, "risk": "LOW", "score": 15},
        {"id": "rohit.kumar@oksbi", "label": "Rohit Kumar", "role": "normal", "type": "Payer", "inflow": 0.0, "outflow": 860.0, "risk": "LOW", "score": 10},
        {"id": "priya.verma@okaxis", "label": "Priya Verma", "role": "normal", "type": "Payer", "inflow": 0.0, "outflow": 1200.0, "risk": "LOW", "score": 15},
        {"id": "vikram.singh@okhdfc", "label": "Vikram Singh", "role": "normal", "type": "Payer", "inflow": 0.0, "outflow": 100.0, "risk": "LOW", "score": 10},
        {"id": "grocery.fresh@okhdfc", "label": "Fresh Groceries Supermarket", "role": "merchant", "type": "Merchant", "inflow": 1470.0, "outflow": 0.0, "risk": "LOW", "score": 10},
        {"id": "coffee.roasters@okicici", "label": "Artisan Coffee Roasters", "role": "merchant", "type": "Merchant", "inflow": 240.0, "outflow": 0.0, "risk": "LOW", "score": 10},
        {"id": "utility.power@okicici", "label": "State Electricity Board", "role": "utility", "type": "Utility Biller", "inflow": 2100.0, "outflow": 0.0, "risk": "LOW", "score": 10},
        {"id": "metro.transit@okaxis", "label": "Metropolitan Transit Rail", "role": "merchant", "type": "Transit Agency", "inflow": 100.0, "outflow": 0.0, "risk": "LOW", "score": 10},
    ]

    normal_edges = [
        {
            "id": "syn-norm-001",
            "source": "alice.sharma@okaxis",
            "target": "grocery.fresh@okhdfc",
            "amount": 850.0,
            "timestamp": (t0 + timedelta(hours=8, minutes=15)).isoformat(),
            "time_offset": "T+00:00",
            "time_delta_sec": 0,
            "hour": 10,
            "score": 10,
            "risk": "LOW",
            "decision": "APPROVED_SIMULATION",
            "typical_amount": 900.0,
            "recent_count": 1,
            "new_recipient": False,
            "reasons": ["Standard merchant grocery payment", "Within typical spending profile [SYNTHETIC DEMO]"],
            "category": "Retail Grocery"
        },
        {
            "id": "syn-norm-002",
            "source": "rohit.kumar@oksbi",
            "target": "coffee.roasters@okicici",
            "amount": 240.0,
            "timestamp": (t0 + timedelta(hours=9, minutes=0)).isoformat(),
            "time_offset": "T+00:45",
            "time_delta_sec": 2700,
            "hour": 11,
            "score": 15,
            "risk": "LOW",
            "decision": "APPROVED_SIMULATION",
            "typical_amount": 250.0,
            "recent_count": 1,
            "new_recipient": False,
            "reasons": ["Morning cafe beverage", "Normal daytime transaction [SYNTHETIC DEMO]"],
            "category": "Dining & Cafe"
        },
        {
            "id": "syn-norm-003",
            "source": "priya.verma@okaxis",
            "target": "alice.sharma@okaxis",
            "amount": 1200.0,
            "timestamp": (t0 + timedelta(hours=9, minutes=45)).isoformat(),
            "time_offset": "T+01:30",
            "time_delta_sec": 2700,
            "hour": 11,
            "score": 20,
            "risk": "LOW",
            "decision": "APPROVED_SIMULATION",
            "typical_amount": 1000.0,
            "recent_count": 1,
            "new_recipient": False,
            "reasons": ["Peer-to-peer dinner bill split", "Known recipient history [SYNTHETIC DEMO]"],
            "category": "P2P Reimbursement"
        },
        {
            "id": "syn-norm-004",
            "source": "vikram.singh@okhdfc",
            "target": "metro.transit@okaxis",
            "amount": 100.0,
            "timestamp": (t0 + timedelta(hours=10, minutes=25)).isoformat(),
            "time_offset": "T+02:10",
            "time_delta_sec": 2400,
            "hour": 12,
            "score": 10,
            "risk": "LOW",
            "decision": "APPROVED_SIMULATION",
            "typical_amount": 120.0,
            "recent_count": 1,
            "new_recipient": False,
            "reasons": ["Daily transit metro fare", "Regular recurring trip [SYNTHETIC DEMO]"],
            "category": "Transit Fare"
        },
        {
            "id": "syn-norm-005",
            "source": "alice.sharma@okaxis",
            "target": "utility.power@okicici",
            "amount": 2100.0,
            "timestamp": (t0 + timedelta(hours=11, minutes=15)).isoformat(),
            "time_offset": "T+03:00",
            "time_delta_sec": 3000,
            "hour": 13,
            "score": 25,
            "risk": "LOW",
            "decision": "APPROVED_SIMULATION",
            "typical_amount": 2000.0,
            "recent_count": 2,
            "new_recipient": False,
            "reasons": ["Monthly electricity bill payment", "Registered biller transaction [SYNTHETIC DEMO]"],
            "category": "Utility Bill"
        },
        {
            "id": "syn-norm-006",
            "source": "rohit.kumar@oksbi",
            "target": "grocery.fresh@okhdfc",
            "amount": 620.0,
            "timestamp": (t0 + timedelta(hours=12, minutes=30)).isoformat(),
            "time_offset": "T+04:15",
            "time_delta_sec": 4500,
            "hour": 14,
            "score": 10,
            "risk": "LOW",
            "decision": "APPROVED_SIMULATION",
            "typical_amount": 500.0,
            "recent_count": 2,
            "new_recipient": False,
            "reasons": ["Afternoon convenience grocery run", "Standard retail merchant [SYNTHETIC DEMO]"],
            "category": "Retail Grocery"
        }
    ]

    normal_scenario = {
        "id": "normal_activity",
        "name": "Normal Activity (Dispersed Commerce)",
        "badge": "BENIGN BASELINE",
        "risk": "LOW",
        "overall_score": 18,
        "description": "Standard peer-to-peer and merchant payments across independent retail, utility, and commute channels during daytime hours with no aggregation or relay.",
        "nodes": normal_nodes,
        "edges": normal_edges,
        "metrics": {
            "total_volume": 5110.0,
            "transaction_count": 6,
            "node_count": len(normal_nodes),
            "fan_in_ratio": "1.2 : 1",
            "fan_out_ratio": "1.5 : 1",
            "avg_interval_min": 51.0,
            "velocity_inr_per_min": 20.04,
            "retention_rate": "Settled at endpoints",
            "time_span": "4 hours 15 minutes"
        },
        "evidence": {
            "pattern_type": "Decentralized Normal Activity",
            "confidence": "HIGH (Benign)",
            "summary": "Decentralized graph topology with balanced in/out degrees. Transactions occur during regular daytime hours (10:15 - 14:30) with expected consumer spending amounts.",
            "indicators": [
                {"signal": "Dispersed Network", "severity": "info", "detail": "Multiple independent payees (groceries, utilities, cafe, transit) with low clustering."},
                {"signal": "Normal Timing", "severity": "info", "detail": "Payments spaced evenly over 4+ hours during daytime business hours."},
                {"signal": "Expected Baselines", "severity": "info", "detail": "Amounts (₹100 - ₹2,100) match typical user baselines with zero sudden spikes."},
                {"signal": "Zero Relay / Drain", "severity": "info", "detail": "No intermediate node forwards received funds; all settlements are terminal."}
            ]
        }
    }

    # 2. MULE FUNNEL SCENARIO
    mule_nodes = [
        {"id": "victim.rahul@okaxis", "label": "Rahul M. (Victim 1)", "role": "source", "type": "Victim Source", "inflow": 0.0, "outflow": 35000.0, "risk": "HIGH", "score": 85},
        {"id": "victim.sneha@oksbi", "label": "Sneha P. (Victim 2)", "role": "source", "type": "Victim Source", "inflow": 0.0, "outflow": 42000.0, "risk": "HIGH", "score": 88},
        {"id": "victim.arjun@okhdfc", "label": "Arjun K. (Victim 3)", "role": "source", "type": "Victim Source", "inflow": 0.0, "outflow": 28500.0, "risk": "HIGH", "score": 85},
        {"id": "victim.pooja@okicici", "label": "Pooja V. (Victim 4)", "role": "source", "type": "Victim Source", "inflow": 0.0, "outflow": 39000.0, "risk": "HIGH", "score": 88},
        {"id": "victim.karan@paytm", "label": "Karan S. (Victim 5)", "role": "source", "type": "Victim Source", "inflow": 0.0, "outflow": 31500.0, "risk": "HIGH", "score": 85},
        {"id": "victim.meera@okaxis", "label": "Meera T. (Victim 6)", "role": "source", "type": "Victim Source", "inflow": 0.0, "outflow": 44000.0, "risk": "HIGH", "score": 92},
        {"id": "mule.aggregator@okhdfc", "label": "Aggregator Mule Intermediary", "role": "mule", "type": "Money Mule", "inflow": 220000.0, "outflow": 215000.0, "risk": "HIGH", "score": 96},
        {"id": "exit.crypto_drain@okaxis", "label": "Offshore Crypto Cash-Out", "role": "exit", "type": "Exit Node", "inflow": 215000.0, "outflow": 0.0, "risk": "HIGH", "score": 98},
    ]

    mule_edges = [
        {
            "id": "syn-mule-001",
            "source": "victim.rahul@okaxis",
            "target": "mule.aggregator@okhdfc",
            "amount": 35000.0,
            "timestamp": (t0 + timedelta(minutes=5)).isoformat(),
            "time_offset": "T+00:00",
            "time_delta_sec": 0,
            "hour": 2,
            "score": 85,
            "risk": "HIGH",
            "decision": "HOLD_FOR_REVIEW",
            "typical_amount": 2000.0,
            "recent_count": 6,
            "new_recipient": True,
            "reasons": ["Amount exceeds five times typical payment (17.5x)", "Recipient has no previous payment history", "Payment initiated during overnight hours (02:05 AM)", "Five or more payments in the last hour [SYNTHETIC DEMO]"],
            "category": "Inbound Mule Funnel"
        },
        {
            "id": "syn-mule-002",
            "source": "victim.sneha@oksbi",
            "target": "mule.aggregator@okhdfc",
            "amount": 42000.0,
            "timestamp": (t0 + timedelta(minutes=13)).isoformat(),
            "time_offset": "T+00:08",
            "time_delta_sec": 480,
            "hour": 2,
            "score": 88,
            "risk": "HIGH",
            "decision": "HOLD_FOR_REVIEW",
            "typical_amount": 1800.0,
            "recent_count": 6,
            "new_recipient": True,
            "reasons": ["Amount exceeds five times typical payment (23.3x)", "Recipient has no previous payment history", "Overnight payment burst (02:13 AM)", "High velocity aggregation [SYNTHETIC DEMO]"],
            "category": "Inbound Mule Funnel"
        },
        {
            "id": "syn-mule-003",
            "source": "victim.arjun@okhdfc",
            "target": "mule.aggregator@okhdfc",
            "amount": 28500.0,
            "timestamp": (t0 + timedelta(minutes=20)).isoformat(),
            "time_offset": "T+00:15",
            "time_delta_sec": 420,
            "hour": 2,
            "score": 85,
            "risk": "HIGH",
            "decision": "HOLD_FOR_REVIEW",
            "typical_amount": 1500.0,
            "recent_count": 6,
            "new_recipient": True,
            "reasons": ["Amount exceeds five times typical payment (19.0x)", "Recipient has no previous payment history", "Overnight high-value transfer (02:20 AM) [SYNTHETIC DEMO]"],
            "category": "Inbound Mule Funnel"
        },
        {
            "id": "syn-mule-004",
            "source": "victim.pooja@okicici",
            "target": "mule.aggregator@okhdfc",
            "amount": 39000.0,
            "timestamp": (t0 + timedelta(minutes=27)).isoformat(),
            "time_offset": "T+00:22",
            "time_delta_sec": 420,
            "hour": 2,
            "score": 88,
            "risk": "HIGH",
            "decision": "HOLD_FOR_REVIEW",
            "typical_amount": 2200.0,
            "recent_count": 6,
            "new_recipient": True,
            "reasons": ["Amount exceeds five times typical payment (17.7x)", "Recipient has no previous payment history", "Suspicious overnight funneling (02:27 AM) [SYNTHETIC DEMO]"],
            "category": "Inbound Mule Funnel"
        },
        {
            "id": "syn-mule-005",
            "source": "victim.karan@paytm",
            "target": "mule.aggregator@okhdfc",
            "amount": 31500.0,
            "timestamp": (t0 + timedelta(minutes=35)).isoformat(),
            "time_offset": "T+00:30",
            "time_delta_sec": 480,
            "hour": 2,
            "score": 85,
            "risk": "HIGH",
            "decision": "HOLD_FOR_REVIEW",
            "typical_amount": 2000.0,
            "recent_count": 6,
            "new_recipient": True,
            "reasons": ["Amount exceeds five times typical payment (15.7x)", "Overnight payment burst (02:35 AM)", "Repeated funnel target [SYNTHETIC DEMO]"],
            "category": "Inbound Mule Funnel"
        },
        {
            "id": "syn-mule-006",
            "source": "victim.meera@okaxis",
            "target": "mule.aggregator@okhdfc",
            "amount": 44000.0,
            "timestamp": (t0 + timedelta(minutes=43)).isoformat(),
            "time_offset": "T+00:38",
            "time_delta_sec": 480,
            "hour": 2,
            "score": 92,
            "risk": "HIGH",
            "decision": "HOLD_FOR_REVIEW",
            "typical_amount": 2500.0,
            "recent_count": 7,
            "new_recipient": True,
            "reasons": ["Amount exceeds five times typical payment (17.6x)", "Recipient has no previous payment history", "Final burst deposit before exit sweep (02:43 AM) [SYNTHETIC DEMO]"],
            "category": "Inbound Mule Funnel"
        },
        {
            "id": "syn-mule-007",
            "source": "mule.aggregator@okhdfc",
            "target": "exit.crypto_drain@okaxis",
            "amount": 215000.0,
            "timestamp": (t0 + timedelta(minutes=47)).isoformat(),
            "time_offset": "T+00:42",
            "time_delta_sec": 240,
            "hour": 2,
            "score": 98,
            "risk": "HIGH",
            "decision": "HOLD_FOR_REVIEW",
            "typical_amount": 5000.0,
            "recent_count": 8,
            "new_recipient": True,
            "reasons": ["Extreme bulk sweep-out of aggregated funds", "Sweep initiated 4 minutes after final victim deposit", "97.7% of aggregated balance drained to exit wallet", "Critical overnight exfiltration alert (02:47 AM) [SYNTHETIC DEMO]"],
            "category": "Outbound Exit Sweep"
        }
    ]

    mule_scenario = {
        "id": "mule_funnel",
        "name": "Mule Funnel (Fan-In Aggregator)",
        "badge": "CRITICAL ANOMALY",
        "risk": "HIGH",
        "overall_score": 94,
        "description": "Six distinct victim accounts funnel ₹220,000 into a single intermediary aggregator mule account within 38 minutes during overnight hours, followed immediately by a ₹215,000 exit sweep.",
        "nodes": mule_nodes,
        "edges": mule_edges,
        "metrics": {
            "total_volume": 435000.0,
            "inflow_volume": 220000.0,
            "sweep_volume": 215000.0,
            "transaction_count": 7,
            "node_count": len(mule_nodes),
            "fan_in_ratio": "6 : 1",
            "fan_out_ratio": "1 : 1",
            "retention_rate": "2.27% (₹5,000 retained)",
            "sweep_latency": "4 minutes post-aggregation",
            "time_span": "42 minutes"
        },
        "evidence": {
            "pattern_type": "Mule Funnel Aggregator & Fast Sweep",
            "confidence": "VERY HIGH (Demonstration)",
            "summary": "Classic fan-in topology where 6 independent accounts route substantial funds into a single intermediary account (mule.aggregator@okhdfc) between 02:05 AM and 02:43 AM, followed 4 minutes later by an immediate 97.7% cash-out sweep.",
            "indicators": [
                {"signal": "Severe Fan-In Disparity", "severity": "critical", "detail": "6 distinct payers funneling into 1 common recipient in under 40 minutes."},
                {"signal": "Rapid Cash-Out Sweep", "severity": "critical", "detail": "97.7% of aggregated capital (₹215,000 of ₹220,000) exited within 240 seconds of the final deposit."},
                {"signal": "Temporal Clustering", "severity": "high", "detail": "All transactions concentrated between 02:05 AM and 02:47 AM (low-traffic overnight window)."},
                {"signal": "Exceeded Payer Limits", "severity": "high", "detail": "Every incoming transfer exceeded each payer's historical baseline by 15x to 23x."}
            ]
        }
    }

    # 3. RAPID PASS-THROUGH (LAYERING RELAY) SCENARIO
    pass_nodes = [
        {"id": "source.victim@okaxis", "label": "Compromised Payer (Origin)", "role": "source", "type": "Victim Source", "inflow": 0.0, "outflow": 98000.0, "risk": "HIGH", "score": 85},
        {"id": "layer1.relay@okhdfc", "label": "Layer 1 Transit Relay", "role": "relay", "type": "Intermediary Hop", "inflow": 98000.0, "outflow": 96500.0, "risk": "HIGH", "score": 92},
        {"id": "layer2.transit@oksbi", "label": "Layer 2 Mule Node", "role": "relay", "type": "Intermediary Hop", "inflow": 96500.0, "outflow": 95000.0, "risk": "HIGH", "score": 95},
        {"id": "layer3.intermediary@okicici", "label": "Layer 3 Shadow Hop", "role": "relay", "type": "Intermediary Hop", "inflow": 95000.0, "outflow": 93800.0, "risk": "HIGH", "score": 96},
        {"id": "layer4.mule@paytm", "label": "Layer 4 Terminal Mule", "role": "relay", "type": "Intermediary Hop", "inflow": 93800.0, "outflow": 92500.0, "risk": "HIGH", "score": 96},
        {"id": "exit.untraceable@okaxis", "label": "Off-Ramp Cash-Out Wallet", "role": "exit", "type": "Exit Node", "inflow": 92500.0, "outflow": 0.0, "risk": "HIGH", "score": 98},
    ]

    pass_edges = [
        {
            "id": "syn-pass-001",
            "source": "source.victim@okaxis",
            "target": "layer1.relay@okhdfc",
            "amount": 98000.0,
            "timestamp": (t0 + timedelta(hours=1, minutes=10, seconds=0)).isoformat(),
            "time_offset": "T+00:00",
            "time_delta_sec": 0,
            "hour": 3,
            "score": 85,
            "risk": "HIGH",
            "decision": "HOLD_FOR_REVIEW",
            "typical_amount": 2500.0,
            "recent_count": 5,
            "new_recipient": True,
            "reasons": ["Amount exceeds five times typical payment (39.2x)", "Overnight payment initiation (03:10:00 AM)", "Initiation of multi-hop rapid chain [SYNTHETIC DEMO]"],
            "category": "Hop 1: Stolen Origin"
        },
        {
            "id": "syn-pass-002",
            "source": "layer1.relay@okhdfc",
            "target": "layer2.transit@oksbi",
            "amount": 96500.0,
            "timestamp": (t0 + timedelta(hours=1, minutes=11, seconds=12)).isoformat(),
            "time_offset": "T+01:12",
            "time_delta_sec": 72,
            "hour": 3,
            "score": 92,
            "risk": "HIGH",
            "decision": "HOLD_FOR_REVIEW",
            "typical_amount": 3000.0,
            "recent_count": 6,
            "new_recipient": True,
            "reasons": ["Rapid forward payment in 72 seconds", "Retained only ₹1,500 (1.53% commission peel)", "Overnight automated pass-through [SYNTHETIC DEMO]"],
            "category": "Hop 2: Rapid Relay"
        },
        {
            "id": "syn-pass-003",
            "source": "layer2.transit@oksbi",
            "target": "layer3.intermediary@okicici",
            "amount": 95000.0,
            "timestamp": (t0 + timedelta(hours=1, minutes=12, seconds=20)).isoformat(),
            "time_offset": "T+02:20",
            "time_delta_sec": 68,
            "hour": 3,
            "score": 95,
            "risk": "HIGH",
            "decision": "HOLD_FOR_REVIEW",
            "typical_amount": 3000.0,
            "recent_count": 7,
            "new_recipient": True,
            "reasons": ["Sub-70s transit latency (68s elapsed)", "Retained ₹1,500 (1.55% commission peel)", "Layering chain velocity alert [SYNTHETIC DEMO]"],
            "category": "Hop 3: Rapid Relay"
        },
        {
            "id": "syn-pass-004",
            "source": "layer3.intermediary@okicici",
            "target": "layer4.mule@paytm",
            "amount": 93800.0,
            "timestamp": (t0 + timedelta(hours=1, minutes=13, seconds=35)).isoformat(),
            "time_offset": "T+03:35",
            "time_delta_sec": 75,
            "hour": 3,
            "score": 96,
            "risk": "HIGH",
            "decision": "HOLD_FOR_REVIEW",
            "typical_amount": 2500.0,
            "recent_count": 8,
            "new_recipient": True,
            "reasons": ["Rapid forward in 75 seconds", "Retained ₹1,200 (1.26% commission peel)", "Penultimate hop in money layering path [SYNTHETIC DEMO]"],
            "category": "Hop 4: Rapid Relay"
        },
        {
            "id": "syn-pass-005",
            "source": "layer4.mule@paytm",
            "target": "exit.untraceable@okaxis",
            "amount": 92500.0,
            "timestamp": (t0 + timedelta(hours=1, minutes=14, seconds=46)).isoformat(),
            "time_offset": "T+04:46",
            "time_delta_sec": 71,
            "hour": 3,
            "score": 98,
            "risk": "HIGH",
            "decision": "HOLD_FOR_REVIEW",
            "typical_amount": 3000.0,
            "recent_count": 9,
            "new_recipient": True,
            "reasons": ["Terminal exit hop reaching unverified cash-out node", "5 consecutive hops completed in under 5 minutes (286s)", "94.39% of initial capital reached destination [SYNTHETIC DEMO]"],
            "category": "Hop 5: Exit Terminal"
        }
    ]

    pass_scenario = {
        "id": "rapid_pass_through",
        "name": "Rapid Pass-Through (Layering Relay)",
        "badge": "CRITICAL ANOMALY",
        "risk": "HIGH",
        "overall_score": 98,
        "description": "High-velocity linear peeling chain traversing 5 accounts in 4 minutes 46 seconds (average 71.5 seconds per hop) with minimal balance retention to obfuscate origin.",
        "nodes": pass_nodes,
        "edges": pass_edges,
        "metrics": {
            "total_chain_volume": 475800.0,
            "initial_amount": 98000.0,
            "final_exit_amount": 92500.0,
            "hop_count": 5,
            "node_count": len(pass_nodes),
            "total_duration_sec": 286,
            "avg_hop_latency_sec": 71.5,
            "avg_peel_per_hop": "1.41% (₹1,375 avg commission)",
            "retention_rate": "5.61% total across all 4 relay hops",
            "time_span": "4 minutes 46 seconds"
        },
        "evidence": {
            "pattern_type": "Rapid Multi-Hop Layering / Peeling Chain",
            "confidence": "VERY HIGH (Demonstration)",
            "summary": "Linear relay topology showing automated high-frequency transfers across 4 intermediate mule nodes. Each hop forwards 98.5% of incoming funds within 68 to 75 seconds, characteristic of programmatic money laundering.",
            "indicators": [
                {"signal": "Programmatic Velocity", "severity": "critical", "detail": "Average hop time delta of 71.5 seconds strongly indicates scripted/automated execution rather than manual user interaction."},
                {"signal": "Uniform Peeling Fee", "severity": "critical", "detail": "Each intermediate hop retains exactly 1.2% - 1.5% as an automated commission before immediate relay."},
                {"signal": "Zero Account Retention", "severity": "high", "detail": "Intermediary nodes maintain negligible balances, operating purely as transient transit relays."},
                {"signal": "Layering Obfuscation", "severity": "high", "detail": "5 distinct banking handles across 4 UPI provider domains crossed in 286 seconds."}
            ]
        }
    }

    return {
        "normal_activity": normal_scenario,
        "mule_funnel": mule_scenario,
        "rapid_pass_through": pass_scenario
    }

@router.get("/scenarios")
def list_scenarios():
    """List available deterministic scenarios for the network explorer."""
    scenarios = build_scenarios()
    return [
        {
            "id": s["id"],
            "name": s["name"],
            "badge": s["badge"],
            "risk": s["risk"],
            "overall_score": s["overall_score"],
            "description": s["description"],
            "node_count": len(s["nodes"]),
            "edge_count": len(s["edges"])
        }
        for s in scenarios.values()
    ]

@router.get("/graph")
def get_graph(scenario_id: str = Query("mule_funnel", description="Scenario identifier")):
    """Get the network graph, timeline, metrics, and evidence for a scenario."""
    scenarios = build_scenarios()
    if scenario_id not in scenarios:
        raise HTTPException(404, f"Scenario '{scenario_id}' not found. Choose from: {list(scenarios.keys())}")
    
    scenario = scenarios[scenario_id]
    return {
        **scenario,
        "synthetic_notice": "SYNTHETIC DEMONSTRATION DATA • Pattern recognition based on deterministic graph rules. Not calibrated real-world fraud accuracy. No real bank or UPI connections."
    }

class SeedResponse(BaseModel):
    message: str
    scenario_id: str
    inserted_count: int
    existing_count: int
    case_ids: List[str]

@router.post("/seed", response_model=SeedResponse)
def seed_scenario_to_investigation(
    scenario_id: str = Query("mule_funnel", description="Scenario identifier to seed into active cases"),
    db: Session = Depends(get_db)
):
    """Seed the transactions of a deterministic scenario into the active Transaction database.
    Allows fraud analysts to immediately investigate related synthetic transactions in the existing investigation workflow.
    """
    scenarios = build_scenarios()
    if scenario_id not in scenarios:
        raise HTTPException(404, f"Scenario '{scenario_id}' not found")
    
    scenario = scenarios[scenario_id]
    edges = scenario["edges"]
    
    inserted = 0
    existing = 0
    case_ids = []

    for edge in edges:
        existing_t = db.get(Transaction, edge["id"])
        if existing_t:
            existing += 1
            if existing_t.risk == "HIGH":
                case_ids.append(existing_t.id)
            continue
        
        # Parse timestamp
        ts = datetime.fromisoformat(edge["timestamp"])
        
        # Insert into Transaction table
        t = Transaction(
            id=edge["id"],
            timestamp=ts,
            amount=float(edge["amount"]),
            recipient_upi=edge["target"],
            typical_amount=float(edge.get("typical_amount", 2000.0)),
            recent_count=int(edge.get("recent_count", 1)),
            hour=int(edge.get("hour", 2)),
            new_recipient=bool(edge.get("new_recipient", False)),
            score=int(edge["score"]),
            risk=edge["risk"],
            decision=edge["decision"],
            reasons=json.dumps(edge["reasons"]),
            model=f"synthetic-network-demo:{scenario_id}",
            review_status="OPEN" if edge["risk"] == "HIGH" else "CLOSED",
            reviewer_note=f"Synthetic demonstration record for {scenario['name']}."
        )
        db.add(t)
        inserted += 1
        if edge["risk"] == "HIGH":
            case_ids.append(t.id)

    db.commit()

    return SeedResponse(
        message=f"Seeded {inserted} synthetic transactions from '{scenario['name']}' into database ({existing} already present).",
        scenario_id=scenario_id,
        inserted_count=inserted,
        existing_count=existing,
        case_ids=case_ids
    )

@router.get("/transaction/{transaction_id}")
def get_transaction_network_context(transaction_id: str, db: Session = Depends(get_db)):
    """Fetch enriched network context for a transaction to bridge Network Explorer and Case Manager."""
    t = db.get(Transaction, transaction_id)
    if not t:
        raise HTTPException(404, "Transaction not found")
    
    # Check if this transaction matches one of our deterministic scenarios
    scenarios = build_scenarios()
    matched_scenario = None
    matched_edge = None

    for s in scenarios.values():
        for e in s["edges"]:
            if e["id"] == transaction_id:
                matched_scenario = s
                matched_edge = e
                break
        if matched_edge:
            break
    
    return {
        "id": t.id,
        "timestamp": t.timestamp.isoformat() if t.timestamp else None,
        "amount": t.amount,
        "recipient_upi": t.recipient_upi,
        "risk": t.risk,
        "score": t.score,
        "decision": t.decision,
        "review_status": t.review_status,
        "reviewer_note": t.reviewer_note,
        "model": t.model,
        "reasons": json.loads(t.reasons),
        "network_context": {
            "is_synthetic_network": matched_edge is not None,
            "scenario_id": matched_scenario["id"] if matched_scenario else None,
            "scenario_name": matched_scenario["name"] if matched_scenario else None,
            "sender_upi": matched_edge["source"] if matched_edge else None,
            "time_offset": matched_edge["time_offset"] if matched_edge else None,
            "time_delta_sec": matched_edge["time_delta_sec"] if matched_edge else None,
            "category": matched_edge["category"] if matched_edge else None,
            "pattern_summary": matched_scenario["evidence"]["summary"] if matched_scenario else None
        }
    }
