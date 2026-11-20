"""Tests for Synthetic Fraud Network Explorer API."""
import os
os.environ['DATABASE_URL'] = 'sqlite:///./test_fraudshield.db'
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_list_scenarios():
    response = client.get('/api/network/scenarios')
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 3
    ids = {s['id'] for s in data}
    assert ids == {'normal_activity', 'mule_funnel', 'rapid_pass_through'}
    for s in data:
        assert 'name' in s
        assert 'badge' in s
        assert 'risk' in s
        assert 'overall_score' in s
        assert 'node_count' in s
        assert 'edge_count' in s

def test_normal_activity_graph():
    response = client.get('/api/network/graph?scenario_id=normal_activity')
    assert response.status_code == 200
    data = response.json()
    assert data['id'] == 'normal_activity'
    assert data['risk'] == 'LOW'
    assert data['overall_score'] <= 30
    assert len(data['nodes']) >= 6
    assert len(data['edges']) >= 5
    assert 'metrics' in data
    assert 'evidence' in data
    assert 'synthetic_notice' in data
    assert 'SYNTHETIC' in data['synthetic_notice']
    assert data['evidence']['pattern_type'] == 'Decentralized Normal Activity'

def test_mule_funnel_graph():
    response = client.get('/api/network/graph?scenario_id=mule_funnel')
    assert response.status_code == 200
    data = response.json()
    assert data['id'] == 'mule_funnel'
    assert data['risk'] == 'HIGH'
    assert data['overall_score'] >= 85
    assert data['metrics']['fan_in_ratio'] == '6 : 1'
    assert data['metrics']['sweep_volume'] == 215000.0
    # Check that aggregator node exists
    nodes_by_id = {n['id']: n for n in data['nodes']}
    assert 'mule.aggregator@okhdfc' in nodes_by_id
    assert nodes_by_id['mule.aggregator@okhdfc']['role'] == 'mule'
    assert 'exit.crypto_drain@okaxis' in nodes_by_id
    # Check evidence indicators
    indicators = data['evidence']['indicators']
    assert any('Fan-In' in ind['signal'] for ind in indicators)
    assert any('Sweep' in ind['signal'] for ind in indicators)

def test_rapid_pass_through_graph():
    response = client.get('/api/network/graph?scenario_id=rapid_pass_through')
    assert response.status_code == 200
    data = response.json()
    assert data['id'] == 'rapid_pass_through'
    assert data['risk'] == 'HIGH'
    assert data['overall_score'] >= 90
    assert data['metrics']['hop_count'] == 5
    assert data['metrics']['avg_hop_latency_sec'] < 90.0
    assert len(data['edges']) == 5
    # Verify sequential time offsets
    for i in range(1, len(data['edges'])):
        assert data['edges'][i]['time_delta_sec'] > 0

def test_invalid_scenario_404():
    response = client.get('/api/network/graph?scenario_id=non_existent')
    assert response.status_code == 404

def test_seed_and_investigate_workflow():
    # Seed the mule funnel scenario
    seed_res = client.post('/api/network/seed?scenario_id=mule_funnel')
    assert seed_res.status_code == 200
    seed_data = seed_res.json()
    assert seed_data['scenario_id'] == 'mule_funnel'
    assert seed_data['inserted_count'] + seed_data['existing_count'] >= 7
    assert len(seed_data['case_ids']) >= 6

    # Verify transactions now appear in /api/transactions
    tx_res = client.get('/api/transactions?limit=100')
    assert tx_res.status_code == 200
    all_tx = tx_res.json()
    tx_ids = {t['id'] for t in all_tx}
    assert 'syn-mule-001' in tx_ids
    assert 'syn-mule-007' in tx_ids

    # Verify high-risk synthetic transactions appear in /api/cases
    cases_res = client.get('/api/cases')
    assert cases_res.status_code == 200
    case_ids = {c['id'] for c in cases_res.json()}
    assert 'syn-mule-001' in case_ids

    # Verify network context lookup endpoint
    ctx_res = client.get('/api/network/transaction/syn-mule-001')
    assert ctx_res.status_code == 200
    ctx_data = ctx_res.json()
    assert ctx_data['id'] == 'syn-mule-001'
    assert ctx_data['network_context']['is_synthetic_network'] is True
    assert ctx_data['network_context']['scenario_id'] == 'mule_funnel'
    assert ctx_data['network_context']['sender_upi'] == 'victim.rahul@okaxis'
