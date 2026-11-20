import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  Network, Share2, Play, Pause, RotateCcw, ExternalLink, Eye,
  Sliders, Layers, Search, Filter, AlertTriangle, ShieldAlert,
  CheckCircle2, Clock, ArrowRight, Shield, Wallet, Users,
  Activity, Sparkles, ChevronRight, CornerDownRight, Check
} from 'lucide-react';

const NODE_LAYOUTS = {
  normal_activity: {
    'alice.sharma@okaxis': { x: 220, y: 180 },
    'rohit.kumar@oksbi': { x: 180, y: 340 },
    'priya.verma@okaxis': { x: 80, y: 130 },
    'vikram.singh@okhdfc': { x: 110, y: 260 },
    'grocery.fresh@okhdfc': { x: 500, y: 310 },
    'coffee.roasters@okicici': { x: 430, y: 410 },
    'utility.power@okicici': { x: 500, y: 110 },
    'metro.transit@okaxis': { x: 340, y: 260 }
  },
  mule_funnel: {
    'victim.rahul@okaxis': { x: 110, y: 65 },
    'victim.sneha@oksbi': { x: 110, y: 135 },
    'victim.arjun@okhdfc': { x: 110, y: 205 },
    'victim.pooja@okicici': { x: 110, y: 275 },
    'victim.karan@paytm': { x: 110, y: 345 },
    'victim.meera@okaxis': { x: 110, y: 415 },
    'mule.aggregator@okhdfc': { x: 450, y: 240 },
    'exit.crypto_drain@okaxis': { x: 740, y: 240 }
  },
  rapid_pass_through: {
    'source.victim@okaxis': { x: 70, y: 240 },
    'layer1.relay@okhdfc': { x: 210, y: 240 },
    'layer2.transit@oksbi': { x: 350, y: 240 },
    'layer3.intermediary@okicici': { x: 490, y: 240 },
    'layer4.mule@paytm': { x: 630, y: 240 },
    'exit.untraceable@okaxis': { x: 770, y: 240 }
  }
};

export default function NetworkExplorer({ API, session, onOpenInvestigation, refreshGlobalCases }) {
  const [scenarios, setScenarios] = useState([]);
  const [currentScenarioId, setCurrentScenarioId] = useState('mule_funnel');
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Filters
  const [riskFilter, setRiskFilter] = useState('ALL');
  const [roleFilter, setRoleFilter] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');
  const [minAmount, setMinAmount] = useState(0);

  // Interactive Selection
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState(null);
  const [hoveredNodeId, setHoveredNodeId] = useState(null);

  // Timeline & Playback
  const [playbackStep, setPlaybackStep] = useState(-1);
  const [isPlaying, setIsPlaying] = useState(false);
  const playTimerRef = useRef(null);

  // Seeding feedback
  const [seedNotice, setSeedNotice] = useState('');
  const [seedLoading, setSeedLoading] = useState(false);

  // Quick In-place review state
  const [reviewNote, setReviewNote] = useState('');
  const [reviewStatus, setReviewStatus] = useState('UNDER_REVIEW');
  const [reviewMsg, setReviewMsg] = useState('');

  // Fetch scenarios list
  useEffect(() => {
    fetch(`${API}/api/network/scenarios`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        setScenarios(data);
        setError('');
      })
      .catch(err => {
        console.error('Failed to fetch scenarios:', err);
        setError('Failed to load network scenarios. Ensure backend is running.');
      });
  }, [API]);

  // Fetch selected scenario graph data
  useEffect(() => {
    setLoading(true);
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
    setHoveredNodeId(null);
    setPlaybackStep(-1);
    setIsPlaying(false);
    clearInterval(playTimerRef.current);
    setSeedNotice('');
    setReviewMsg('');

    fetch(`${API}/api/network/graph?scenario_id=${currentScenarioId}`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        setGraphData(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load graph data:', err);
        setError(`Failed to load graph: ${err.message}`);
        setLoading(false);
      });
  }, [API, currentScenarioId]);

  // Timeline playback loop
  useEffect(() => {
    if (isPlaying && graphData && graphData.edges.length > 0) {
      playTimerRef.current = setInterval(() => {
        setPlaybackStep(prev => {
          const next = prev + 1;
          if (next >= graphData.edges.length) {
            setIsPlaying(false);
            return prev;
          }
          const activeEdge = graphData.edges[next];
          setSelectedEdgeId(activeEdge.id);
          setSelectedNodeId(activeEdge.target);
          return next;
        });
      }, 1600);
    } else {
      clearInterval(playTimerRef.current);
    }
    return () => clearInterval(playTimerRef.current);
  }, [isPlaying, graphData]);

  // Stop playback when selecting manually
  function handleSelectEdge(edge) {
    setIsPlaying(false);
    setSelectedEdgeId(edge.id);
    setSelectedNodeId(edge.target);
    const edgeIndex = graphData?.edges.findIndex(e => e.id === edge.id);
    if (edgeIndex !== -1 && edgeIndex !== undefined) {
      setPlaybackStep(edgeIndex);
    }
  }

  function handleSelectNode(nodeId) {
    setIsPlaying(false);
    setSelectedNodeId(nodeId);
    setSelectedEdgeId(null);
  }

  function togglePlayback() {
    if (isPlaying) {
      setIsPlaying(false);
    } else {
      if (playbackStep >= (graphData?.edges.length || 0) - 1) {
        setPlaybackStep(-1);
      }
      setIsPlaying(true);
    }
  }

  function resetPlayback() {
    setIsPlaying(false);
    setPlaybackStep(-1);
    setSelectedEdgeId(null);
    setSelectedNodeId(null);
  }

  // Seed scenario into active case management
  async function seedScenario(autoOpenTxId = null) {
    setSeedLoading(true);
    setSeedNotice('');
    try {
      const res = await fetch(`${API}/api/network/seed?scenario_id=${currentScenarioId}`, {
        method: 'POST'
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setSeedNotice(data.message);
      if (refreshGlobalCases) refreshGlobalCases();

      if (autoOpenTxId && onOpenInvestigation) {
        onOpenInvestigation(autoOpenTxId);
      }
    } catch (err) {
      setSeedNotice(`Seed failed: ${err.message}`);
    } finally {
      setSeedLoading(false);
    }
  }

  // In-place review of selected transaction
  async function submitQuickReview(txId) {
    if (!session?.access_token) {
      setReviewMsg('Analyst or Admin login required to submit review.');
      return;
    }
    try {
      // First ensure seeded
      await fetch(`${API}/api/network/seed?scenario_id=${currentScenarioId}`, { method: 'POST' });
      // Update case
      const res = await fetch(`${API}/api/cases/${txId}/workflow`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.access_token}`
        },
        body: JSON.stringify({ status: reviewStatus, note: reviewNote || 'Analyst network graph review' })
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${res.status}`);
      }
      setReviewMsg(`Case #${txId.slice(0, 8)} updated to ${reviewStatus}`);
      setReviewNote('');
      if (refreshGlobalCases) refreshGlobalCases();
    } catch (err) {
      setReviewMsg(`Error updating case: ${err.message}`);
    }
  }

  // Filtered nodes & edges
  const { filteredNodes, filteredEdges, connectedNodeIds } = useMemo(() => {
    if (!graphData) return { filteredNodes: [], filteredEdges: [], connectedNodeIds: new Set() };

    let edges = graphData.edges.filter(edge => {
      if (minAmount > 0 && edge.amount < minAmount) return false;
      if (riskFilter !== 'ALL' && edge.risk !== riskFilter) return false;
      if (searchTerm) {
        const s = searchTerm.toLowerCase();
        const matchesEdge = edge.id.toLowerCase().includes(s) ||
          edge.source.toLowerCase().includes(s) ||
          edge.target.toLowerCase().includes(s);
        if (!matchesEdge) return false;
      }
      return true;
    });

    let nodes = graphData.nodes.filter(node => {
      if (roleFilter !== 'ALL' && node.role !== roleFilter) return false;
      if (riskFilter !== 'ALL' && node.risk !== riskFilter) return false;
      if (searchTerm) {
        const s = searchTerm.toLowerCase();
        const matchesNode = node.id.toLowerCase().includes(s) ||
          node.label.toLowerCase().includes(s);
        const matchesConnectedEdge = edges.some(e => e.source === node.id || e.target === node.id);
        if (!matchesNode && !matchesConnectedEdge) return false;
      }
      return true;
    });

    const connected = new Set();
    const activeFocus = hoveredNodeId || selectedNodeId;
    if (activeFocus) {
      connected.add(activeFocus);
      graphData.edges.forEach(e => {
        if (e.source === activeFocus) connected.add(e.target);
        if (e.target === activeFocus) connected.add(e.source);
      });
    }

    return { filteredNodes: nodes, filteredEdges: edges, connectedNodeIds: connected };
  }, [graphData, riskFilter, roleFilter, searchTerm, minAmount, hoveredNodeId, selectedNodeId]);

  // Selected edge object
  const selectedEdge = useMemo(() => {
    if (!graphData || !selectedEdgeId) return null;
    return graphData.edges.find(e => e.id === selectedEdgeId);
  }, [graphData, selectedEdgeId]);

  // Selected node object
  const selectedNode = useMemo(() => {
    if (!graphData || !selectedNodeId) return null;
    return graphData.nodes.find(n => n.id === selectedNodeId);
  }, [graphData, selectedNodeId]);

  // Positions map for current scenario
  const layout = NODE_LAYOUTS[currentScenarioId] || {};

  return (
    <div className="network-explorer">
      {/* Top Header & Scenario Selector */}
      <section className="panel network-head-panel">
        <div className="panel-head">
          <div>
            <div className="net-eyebrow">
              <Network size={15} /> FLAGSHIP INTELLIGENCE • SYNTHETIC FRAUD GRAPH
            </div>
            <h2>Synthetic Fraud Network Explorer</h2>
            <p className="fine">
              Deterministic scenario simulations revealing synthetic payer/payee relationships, funnel topologies, and high-velocity layering chains.
            </p>
          </div>
          <div className="scenario-actions">
            <button
              className="outline-btn sync-btn"
              disabled={seedLoading}
              onClick={() => seedScenario()}
              title="Seed all scenario transactions into active cases database"
            >
              <Sparkles size={16} />
              {seedLoading ? 'Seeding...' : 'Seed to Case Manager'}
            </button>
          </div>
        </div>

        {/* Scenario Selection Tabs */}
        <div className="scenario-tabs">
          {scenarios.map(s => {
            const isSelected = s.id === currentScenarioId;
            return (
              <button
                key={s.id}
                className={`scenario-card ${isSelected ? 'selected' : ''}`}
                onClick={() => setCurrentScenarioId(s.id)}
              >
                <div className="scenario-card-top">
                  <span className={`scenario-badge ${s.risk.toLowerCase()}`}>
                    {s.badge}
                  </span>
                  <span className="scenario-score">Risk {s.overall_score}/100</span>
                </div>
                <div className="scenario-title">{s.name}</div>
                <div className="scenario-meta">
                  <span>{s.node_count} Accounts</span>
                  <span>•</span>
                  <span>{s.edge_count} Transfers</span>
                </div>
              </button>
            );
          })}
        </div>

        {seedNotice && (
          <div className="feedback-notice">
            <Check size={16} /> {seedNotice}
          </div>
        )}
        {error && <div className="error">{error}</div>}
      </section>

      {/* Filter Toolbar */}
      <section className="panel filter-bar-panel">
        <div className="filter-grid">
          <div className="filter-group search-group">
            <Search size={15} />
            <input
              placeholder="Search VPA, account, or tx ID..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
            />
          </div>

          <div className="filter-group">
            <label>Risk Level:</label>
            <div className="filter-pills mini">
              {['ALL', 'HIGH', 'MEDIUM', 'LOW'].map(r => (
                <button
                  key={r}
                  className={riskFilter === r ? 'selected' : ''}
                  onClick={() => setRiskFilter(r)}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>

          <div className="filter-group">
            <label>Node Role:</label>
            <select
              value={roleFilter}
              onChange={e => setRoleFilter(e.target.value)}
              className="role-select"
            >
              <option value="ALL">All Roles</option>
              <option value="source">Victim / Source</option>
              <option value="mule">Aggregator Mule</option>
              <option value="relay">Layering Hop</option>
              <option value="exit">Exit / Cash-out</option>
              <option value="normal">Normal / Retail</option>
            </select>
          </div>

          <div className="filter-group amount-group">
            <label>Min Amount: ₹{minAmount.toLocaleString('en-IN')}</label>
            <input
              type="range"
              min="0"
              max="100000"
              step="5000"
              value={minAmount}
              onChange={e => setMinAmount(Number(e.target.value))}
            />
          </div>
        </div>
      </section>

      {/* Main Workbench: Interactive Graph Canvas + Details Pane */}
      <div className="network-workbench">
        {/* Graph Canvas */}
        <section className="panel graph-canvas-panel">
          <div className="graph-header">
            <div className="graph-title-group">
              <Share2 size={18} />
              <div>
                <h3>Payer / Payee Relationship Graph</h3>
                <small>Hover nodes to highlight links • Click nodes or directed arrows to inspect</small>
              </div>
            </div>
            <div className="graph-controls">
              <button
                className={`playback-btn ${isPlaying ? 'active' : ''}`}
                onClick={togglePlayback}
                title={isPlaying ? 'Pause flow animation' : 'Play flow animation'}
              >
                {isPlaying ? <Pause size={15} /> : <Play size={15} />}
                <span>{isPlaying ? 'Pause Flow' : 'Play Flow'}</span>
              </button>
              <button
                className="icon-ctrl-btn"
                onClick={resetPlayback}
                title="Reset animation & selection"
              >
                <RotateCcw size={15} />
              </button>
            </div>
          </div>

          {loading ? (
            <div className="canvas-loading">
              <Activity className="spin" size={32} />
              <span>Generating synthetic network topology...</span>
            </div>
          ) : (
            <div className="svg-container">
              <svg
                viewBox="0 0 850 480"
                className="network-svg"
                preserveAspectRatio="xMidYMid meet"
              >
                <defs>
                  {/* Arrow markers */}
                  <marker
                    id="arrow-default"
                    viewBox="0 0 10 10"
                    refX="22"
                    refY="5"
                    markerWidth="6"
                    markerHeight="6"
                    orient="auto-start-reverse"
                  >
                    <path d="M 0 1 L 9 5 L 0 9 z" fill="#44619d" />
                  </marker>
                  <marker
                    id="arrow-high"
                    viewBox="0 0 10 10"
                    refX="22"
                    refY="5"
                    markerWidth="7"
                    markerHeight="7"
                    orient="auto-start-reverse"
                  >
                    <path d="M 0 1 L 9 5 L 0 9 z" fill="#ff6b83" />
                  </marker>
                  <marker
                    id="arrow-active"
                    viewBox="0 0 10 10"
                    refX="22"
                    refY="5"
                    markerWidth="8"
                    markerHeight="8"
                    orient="auto-start-reverse"
                  >
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#ffbf69" />
                  </marker>
                </defs>

                {/* Graph Edges / Transactions */}
                {graphData?.edges.map((edge, idx) => {
                  const sPos = layout[edge.source] || { x: 100, y: 100 };
                  const tPos = layout[edge.target] || { x: 700, y: 300 };

                  const isSelected = selectedEdgeId === edge.id;
                  const isPlaybackActive = playbackStep === idx;
                  const isConnectedToHover = (hoveredNodeId === edge.source || hoveredNodeId === edge.target);
                  const isConnectedToSelect = (selectedNodeId === edge.source || selectedNodeId === edge.target);
                  const isDimmed = (hoveredNodeId || selectedNodeId) && !isConnectedToHover && !isConnectedToSelect;

                  // Curvature calculation
                  const dx = tPos.x - sPos.x;
                  const dy = tPos.y - sPos.y;
                  const cx = (sPos.x + tPos.x) / 2 - dy * 0.12;
                  const cy = (sPos.y + tPos.y) / 2 + dx * 0.12;
                  const pathData = `M ${sPos.x} ${sPos.y} Q ${cx} ${cy} ${tPos.x} ${tPos.y}`;

                  const markerId = isSelected || isPlaybackActive
                    ? 'url(#arrow-active)'
                    : edge.risk === 'HIGH'
                      ? 'url(#arrow-high)'
                      : 'url(#arrow-default)';

                  return (
                    <g
                      key={edge.id}
                      className={`edge-group ${isSelected ? 'selected' : ''} ${isPlaybackActive ? 'playback-active' : ''} ${isDimmed ? 'dimmed' : ''}`}
                      onClick={() => handleSelectEdge(edge)}
                    >
                      {/* Invisible wider hit area for easy clicking */}
                      <path
                        d={pathData}
                        fill="none"
                        stroke="transparent"
                        strokeWidth="20"
                        className="edge-hit-area"
                      />
                      {/* Visible edge line */}
                      <path
                        d={pathData}
                        fill="none"
                        className={`edge-line ${edge.risk.toLowerCase()} ${isPlaybackActive ? 'pulse' : ''}`}
                        markerEnd={markerId}
                      />
                      {/* Edge Label Pill */}
                      <g transform={`translate(${cx}, ${cy})`}>
                        <rect
                          x="-34"
                          y="-10"
                          width="68"
                          height="20"
                          rx="5"
                          className={`edge-label-bg ${edge.risk.toLowerCase()}`}
                        />
                        <text
                          textAnchor="middle"
                          y="4"
                          className="edge-label-text"
                        >
                          ₹{(edge.amount / 1000).toFixed(edge.amount >= 10000 ? 0 : 1)}k
                        </text>
                      </g>
                    </g>
                  );
                })}

                {/* Graph Nodes / Accounts */}
                {graphData?.nodes.map(node => {
                  const pos = layout[node.id] || { x: 400, y: 240 };
                  const isSelected = selectedNodeId === node.id;
                  const isHovered = hoveredNodeId === node.id;
                  const isConnected = connectedNodeIds.has(node.id);
                  const isDimmed = (hoveredNodeId || selectedNodeId) && !isConnected;

                  const radius = node.role === 'mule' ? 26 : node.role === 'exit' ? 24 : 20;

                  return (
                    <g
                      key={node.id}
                      transform={`translate(${pos.x}, ${pos.y})`}
                      className={`node-group role-${node.role} risk-${node.risk.toLowerCase()} ${isSelected ? 'selected' : ''} ${isHovered ? 'hovered' : ''} ${isDimmed ? 'dimmed' : ''}`}
                      onMouseEnter={() => setHoveredNodeId(node.id)}
                      onMouseLeave={() => setHoveredNodeId(null)}
                      onClick={() => handleSelectNode(node.id)}
                    >
                      {/* Pulse ring for key nodes */}
                      {(node.role === 'mule' || node.role === 'exit') && (
                        <circle
                          r={radius + 8}
                          className="node-pulse-ring"
                        />
                      )}
                      {/* Node circle */}
                      <circle
                        r={radius}
                        className={`node-circle role-${node.role} risk-${node.risk.toLowerCase()}`}
                      />
                      {/* Node role letter/glyph */}
                      <text
                        textAnchor="middle"
                        y="5"
                        className="node-glyph"
                      >
                        {node.role === 'mule' ? 'M' : node.role === 'exit' ? 'X' : node.role === 'source' ? 'S' : node.role === 'relay' ? 'R' : 'U'}
                      </text>
                      {/* Node Label (VPA) */}
                      <text
                        textAnchor="middle"
                        y={radius + 15}
                        className="node-label"
                      >
                        {node.label.split(' ')[0]}
                      </text>
                      <text
                        textAnchor="middle"
                        y={radius + 27}
                        className="node-sublabel"
                      >
                        {node.id.split('@')[0]}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
          )}

          {/* Interactive Graph Legend */}
          <div className="graph-legend">
            <div className="legend-item"><span className="legend-dot source" /> Victim / Source</div>
            <div className="legend-item"><span className="legend-dot mule" /> Aggregator Mule</div>
            <div className="legend-item"><span className="legend-dot relay" /> Layering Hop</div>
            <div className="legend-item"><span className="legend-dot exit" /> Cash-Out Exit</div>
            <div className="legend-item"><span className="legend-dot normal" /> Normal Peer / Merchant</div>
          </div>
        </section>

        {/* Right Inspector & Forensic Evidence Column */}
        <section className="panel network-inspector-panel">
          {/* Selected Transaction / Node Inspector */}
          {selectedEdge ? (
            <div className="inspector-card">
              <div className="inspector-header">
                <span className={`status ${selectedEdge.risk.toLowerCase()}`}>
                  {selectedEdge.risk} RISK
                </span>
                <span className="inspector-score">Score: {selectedEdge.score}/100</span>
              </div>
              <h4>Transaction #{selectedEdge.id.slice(0, 12)}</h4>
              <div className="inspector-flow">
                <div className="flow-party">
                  <small>PAYER</small>
                  <b>{selectedEdge.source}</b>
                </div>
                <ArrowRight size={18} className="flow-arrow" />
                <div className="flow-party">
                  <small>PAYEE</small>
                  <b>{selectedEdge.target}</b>
                </div>
              </div>

              <div className="inspector-metrics">
                <div>
                  <small>AMOUNT</small>
                  <strong>₹{selectedEdge.amount.toLocaleString('en-IN')}</strong>
                </div>
                <div>
                  <small>TIMELINE OFFSET</small>
                  <b>{selectedEdge.time_offset}</b>
                </div>
                <div>
                  <small>DECISION</small>
                  <b className="blue">{selectedEdge.decision.replace(/_/g, ' ')}</b>
                </div>
              </div>

              <div className="inspector-reasons">
                <h5>Forensic Indicators</h5>
                <ul>
                  {selectedEdge.reasons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>

              {/* Action Buttons to open in Investigation Workflow */}
              <div className="inspector-actions">
                <button
                  className="primary full invest-btn"
                  onClick={() => seedScenario(selectedEdge.id)}
                >
                  <ExternalLink size={16} /> Open in Investigation Workflow
                </button>
              </div>

              {/* Quick in-place case review if signed in */}
              <div className="quick-review-box">
                <h5>Quick Case Action</h5>
                <p className="fine">Analyst review records are tracked in the audit trail.</p>
                <div className="quick-review-controls">
                  <select
                    value={reviewStatus}
                    onChange={e => setReviewStatus(e.target.value)}
                  >
                    <option value="UNDER_REVIEW">UNDER_REVIEW</option>
                    <option value="CLOSED">CLOSED</option>
                  </select>
                  <button
                    className="outline-btn"
                    onClick={() => submitQuickReview(selectedEdge.id)}
                  >
                    Apply Status
                  </button>
                </div>
                <input
                  placeholder="Case review note (required)..."
                  value={reviewNote}
                  onChange={e => setReviewNote(e.target.value)}
                  className="quick-note-input"
                />
                {reviewMsg && <p className="feedback-small">{reviewMsg}</p>}
              </div>
            </div>
          ) : selectedNode ? (
            <div className="inspector-card">
              <div className="inspector-header">
                <span className={`status ${selectedNode.risk.toLowerCase()}`}>
                  {selectedNode.role.toUpperCase()}
                </span>
                <span className="inspector-score">Score: {selectedNode.score}/100</span>
              </div>
              <h4>{selectedNode.label}</h4>
              <p className="vpa-display">{selectedNode.id}</p>

              <div className="inspector-metrics">
                <div>
                  <small>TOTAL INFLOW</small>
                  <strong className="green">₹{selectedNode.inflow.toLocaleString('en-IN')}</strong>
                </div>
                <div>
                  <small>TOTAL OUTFLOW</small>
                  <strong className="red">₹{selectedNode.outflow.toLocaleString('en-IN')}</strong>
                </div>
              </div>

              <div className="node-incident-list">
                <h5>Connected Payments</h5>
                {graphData?.edges
                  .filter(e => e.source === selectedNode.id || e.target === selectedNode.id)
                  .map(e => (
                    <div
                      key={e.id}
                      className="incident-row"
                      onClick={() => handleSelectEdge(e)}
                    >
                      <span>
                        {e.source === selectedNode.id ? 'Out to ' + e.target.split('@')[0] : 'In from ' + e.source.split('@')[0]}
                      </span>
                      <b>₹{e.amount.toLocaleString('en-IN')}</b>
                    </div>
                  ))}
              </div>
            </div>
          ) : (
            <div className="inspector-card empty-inspector">
              <Eye size={40} />
              <h4>Entity Inspector</h4>
              <p>Click any account node or payment link in the graph or timeline to inspect transaction signals.</p>
            </div>
          )}

          {/* Pattern Evidence Summary Box */}
          <div className="pattern-evidence-box">
            <div className="evidence-header">
              <ShieldAlert size={18} />
              <h4>{graphData?.evidence?.pattern_type || 'Pattern Evidence'}</h4>
            </div>
            <p className="evidence-summary">{graphData?.evidence?.summary}</p>

            <div className="evidence-indicators">
              {graphData?.evidence?.indicators?.map((ind, i) => (
                <div key={i} className={`indicator-item severity-${ind.severity}`}>
                  <div className="indicator-signal">{ind.signal}</div>
                  <div className="indicator-detail">{ind.detail}</div>
                </div>
              ))}
            </div>

            <div className="synthetic-disclaimer">
              <Shield size={16} />
              <small>{graphData?.synthetic_notice}</small>
            </div>
          </div>
        </section>
      </div>

      {/* Interactive Timeline Section */}
      <section className="panel timeline-panel">
        <div className="panel-head">
          <div className="timeline-title-group">
            <Clock size={18} />
            <div>
              <h3>Transfer Sequence Timeline</h3>
              <p className="fine">Chronological progression of synthetic payments across network hops.</p>
            </div>
          </div>
          <span className="tag">
            {graphData?.metrics?.time_span || `${graphData?.edges.length} transfers`}
          </span>
        </div>

        <div className="timeline-strip">
          {graphData?.edges.map((edge, idx) => {
            const isSelected = selectedEdgeId === edge.id;
            const isPlaybackCurrent = playbackStep === idx;
            return (
              <div
                key={edge.id}
                className={`timeline-node-card ${isSelected ? 'selected' : ''} ${isPlaybackCurrent ? 'active-step' : ''}`}
                onClick={() => handleSelectEdge(edge)}
              >
                <div className="time-badge">
                  <span>Step #{idx + 1}</span>
                  <b>{edge.time_offset}</b>
                </div>
                <div className="timeline-amount">
                  ₹{edge.amount.toLocaleString('en-IN')}
                </div>
                <div className="timeline-parties">
                  <span className="source-party">{edge.source.split('@')[0]}</span>
                  <ArrowRight size={12} />
                  <span className="target-party">{edge.target.split('@')[0]}</span>
                </div>
                <div className="timeline-footer">
                  <span className={`micro-status ${edge.risk.toLowerCase()}`}>
                    {edge.risk}
                  </span>
                  <small>{edge.category}</small>
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
