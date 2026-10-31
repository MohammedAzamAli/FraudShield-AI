import {onIdTokenChanged} from 'firebase/auth';
import {auth} from './firebase.js';
import FirebaseSecurity from './FirebaseSecurity.jsx';
import AICopilot from './AICopilot.jsx';
import {SecurityPanel,QRImagePanel,ExplainPanel,CaseManager,ComparisonPanel} from './AdvancedPanels.jsx';
import React,{useState,useEffect} from 'react';
import {ShieldCheck,LayoutDashboard,ArrowLeftRight,Activity,ShieldAlert,CheckCircle2,AlertTriangle,RefreshCw,LockKeyhole,Search,ScanLine,BrainCircuit,ClipboardList,BarChart3,FileDown,Bot,Bell,Wallet,TrendingUp,Clock3,ChevronRight,Download,SlidersHorizontal,UserRound,Shield} from 'lucide-react';
const API=import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const defaults={amount:45000,recipient_upi:'unknown@upi',typical_amount:2000,recent_count:6,hour:2,new_recipient:true};
export default function App(){
 const [analytics,setAnalytics]=useState(null);
 const [session,setSession]=useState(null);
 const [authStatus,setAuthStatus]=useState('signed-out'),[authError,setAuthError]=useState('');
 const [reportError,setReportError]=useState(''),[riskFilter,setRiskFilter]=useState('ALL');
 const [mlResult,setMlResult]=useState(null),[sandboxMetrics,setSandboxMetrics]=useState(null),[adminKey,setAdminKey]=useState(''),[reviewNote,setReviewNote]=useState(''),[reviewMessage,setReviewMessage]=useState('');
 const [page,setPage]=useState('dashboard'),[form,setForm]=useState(defaults),[transactions,setTransactions]=useState([]),[result,setResult]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState(false),[search,setSearch]=useState(''),[metrics,setMetrics]=useState(null),[qr,setQr]=useState('upi://pay?pa=merchant@upi&pn=Demo%20Merchant&am=500'),[qrResult,setQrResult]=useState(null),[cases,setCases]=useState([]),[insights,setInsights]=useState(null);
 useEffect(()=>{
   let active=true;
   const unsubscribe=onIdTokenChanged(auth,async user=>{
     if(!active)return;
     if(!user){setSession(null);setAuthStatus('signed-out');setAuthError('');return;}
     setAuthStatus('checking');setAuthError('');
     try{
       const token=await user.getIdToken();
       const response=await fetch(API+'/api/auth/me',{headers:{Authorization:`Bearer ${token}`}});
       if(!response.ok){
         let detail='';try{const data=await response.json();detail=typeof data.detail==='string'?data.detail:''}catch{}
         if(active){setSession(null);setAuthStatus('error');setAuthError(detail || `Identity check failed (HTTP ${response.status})`)}
         return;
       }
       const profile=await response.json();
       if(active){setSession({access_token:token,user:profile});setAuthStatus('verified');setAuthError('')}
     }catch(error){console.error('Firebase session verification failed:',error);if(active){setSession(null);setAuthStatus('error');setAuthError('Could not contact FastAPI for identity verification')}}
   });
   return ()=>{active=false;unsubscribe()};
 },[]);
 const refresh=async()=>{try{let r=await fetch(API+'/api/transactions');if(!r.ok)throw Error('API error');setTransactions(await r.json());setError('')}catch{setError('Backend offline. Start FastAPI at port 8000.')}};
 
useEffect(() => {
  refresh();
  fetch(API+'/api/analytics').then(r=>r.ok?r.json():null).then(setAnalytics).catch(console.error);

  fetch(API + '/api/ml/sandbox-metrics').then(r=>r.ok?r.json():null).then(setSandboxMetrics).catch(console.error);
  fetch(API + '/api/model/metrics')
    .then(r => r.ok ? r.json() : null)
    .then(setMetrics)
    .catch(error => console.error("Metrics API error:", error));

  fetch(API + '/api/cases')
    .then(r => {
      if (!r.ok) throw new Error(`Cases API: ${r.status}`);
      return r.json();
    })
    .then(setCases)
    .catch(error => console.error("Cases API error:", error));

  fetch(API + '/api/insights')
    .then(r => {
      if (!r.ok) throw new Error(`Insights API: ${r.status}`);
      return r.json();
    })
    .then(setInsights)
    .catch(error => console.error("Insights API error:", error));

  const ws = new WebSocket(API.replace(/^http/, 'ws')+'/ws/alerts');

  ws.onopen = () => {
    console.log("WebSocket connected successfully");
  };

  ws.onmessage = () => {
    refresh();
  fetch(API+'/api/analytics').then(r=>r.ok?r.json():null).then(setAnalytics).catch(console.error);

    fetch(API + '/api/cases')
      .then(r => r.json())
      .then(setCases)
      .catch(error => console.error("Cases refresh error:", error));

    fetch(API + '/api/insights')
      .then(r => r.json())
      .then(setInsights)
      .catch(error => console.error("Insights refresh error:", error));
  };

  ws.onerror = () => {
    console.error("WebSocket connection error");
  };

  return () => {
    ws.close();
  };
}, []);


 const analyze=async(e)=>{e.preventDefault();setLoading(true);setError('');try{const r=await fetch(API+'/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...form,amount:Number(form.amount),typical_amount:Number(form.typical_amount),recent_count:Number(form.recent_count),hour:Number(form.hour)})});if(!r.ok){let x=await r.json();throw Error(JSON.stringify(x.detail||'Request failed'))}const x=await r.json();setResult(x);try{const m=await fetch(API+'/api/ml/sandbox-predict',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...form,amount:Number(form.amount),typical_amount:Number(form.typical_amount),recent_count:Number(form.recent_count),hour:Number(form.hour)})});setMlResult(m.ok?await m.json():null)}catch(e){console.error('Research model unavailable',e);setMlResult(null)}await refresh();fetch(API+'/api/analytics').then(r=>r.json()).then(setAnalytics).catch(console.error)}catch(e){setError(e.message)}finally{setLoading(false)}};
 const high=transactions.filter(x=>x.risk==='HIGH').length,medium=transactions.filter(x=>x.risk==='MEDIUM').length;
 const pages=[['dashboard','Overview',LayoutDashboard],['simulator','UPI Sandbox',ArrowLeftRight],['transactions','Transactions',Activity],['analytics','Analytics',BarChart3],['investigation','Investigations',ClipboardList],['qr','QR Inspector',ScanLine],['model','ML Research',BrainCircuit],['reports','Reports',FileDown],['copilot','AI Fraud Copilot',Bot],['security','Security & Login',UserRound]];
 return <div className="shell"><aside className="sidebar"><div className="brand"><div className="brandmark"><ShieldCheck size={24}/></div><div><b>FraudShield<span>AI</span></b><small>FINANCIAL SECURITY</small></div></div><div className="side-label">WORKSPACE</div><nav>{pages.map(([id,label,Icon])=><button key={id} className={page===id?'active':''} onClick={()=>setPage(id)}><Icon size={18}/>{label}</button>)}</nav><div className="side-bottom"><div className="system-online"><span className="utility-dot"/> SYSTEM ONLINE</div><LockKeyhole size={16}/> Secure sandbox mode<br/><small>No real money transfers</small></div></aside><main><div className="utility-bar"><div className="utility-left"><span className="utility-dot"/> FRAUDSHIELD COMMAND CENTER <span className="utility-divider">/</span> ACADEMIC SANDBOX</div><div className="utility-right"><span className="util-clock"><Clock3 size={14}/> Live session</span><span className="profile"><UserRound size={15}/> Demo workspace</span></div></div><header><div><div className="eyebrow">FRAUD INTELLIGENCE PLATFORM</div><h1>{page==='dashboard'?'Security Overview':page==='simulator'?'UPI Payment Sandbox':page==='investigation'?'Investigation Center':page==='qr'?'UPI QR Inspector':page==='model'?'Model Research Lab':page==='analytics'?'Fraud Analytics':page==='reports'?'Reports & Exports':page==='security'?'Security & Identity':page==='copilot'?'AI Fraud Copilot':'Transaction Intelligence'}</h1><p>Monitor, simulate and investigate payment risk in a controlled environment.</p></div><div className="header-actions"><button className="icon-btn" title="Investigation center" onClick={()=>setPage('investigation')}><Bell size={18}/>{cases.filter(c=>c.review_status!=='CLOSED').length>0&&<span className="notification-dot"/>}</button><span className="live"><i/> Sandbox Active</span><button className="icon-btn" onClick={refresh} title="Refresh"><RefreshCw size={18}/></button></div></header>{error&&<div className="error">{error}</div>}
 {page==='dashboard'&&<><section className="metrics"><div className="metric"><span>Total simulated transactions</span><strong>{transactions.length}</strong><small>Recorded this session</small></div><div className="metric"><span>High-risk alerts</span><strong className="red">{high}</strong><small>Flagged for review</small></div><div className="metric"><span>Medium-risk warnings</span><strong className="amber">{medium}</strong><small>Additional verification</small></div><div className="metric"><span>Low-risk transactions</span><strong className="green">{transactions.length-high-medium}</strong><small>Simulated approval</small></div></section><div className="hero"><div><span className="eyebrow">REAL-TIME RISK INTELLIGENCE</span><h2>Detect suspicious patterns<br/>before simulated payment.</h2><p>Explore transaction behavior, test risk signals and review explainable decisions.</p><button className="primary" onClick={()=>setPage('simulator')}>Launch payment simulator →</button></div><div className="hero-icon"><ShieldCheck size={108}/></div></div><div className="dashboard-visuals"><section className="panel chart-panel"><div className="panel-head"><div><h3>Transaction risk trend</h3><p className="fine">Observed sandbox activity by day</p></div><span className="tag">LAST 7 ACTIVE DAYS</span></div><RiskTrend daily={analytics?.daily||[]}/></section><section className="panel distribution-panel"><div className="panel-head"><h3>Risk distribution</h3><button onClick={()=>setPage('analytics')}>Details <ChevronRight size={14}/></button></div><RiskDonut high={high} medium={medium} low={transactions.length-high-medium}/></section></div><section className="panel recent-panel"><div className="panel-head"><h3>Recent high-risk transactions</h3><button onClick={()=>setPage('investigation')}>View cases <ChevronRight size={14}/></button></div><TransactionTable items={transactions.filter(x=>x.risk==='HIGH').slice(0,4)}/></section><section className="panel"><div className="panel-head"><h3>Recent activity</h3><button onClick={()=>setPage('transactions')}>View all →</button></div><TransactionTable items={transactions.slice(0,5)}/></section></>}
 {page==='simulator'&&<div className="two-col"><section className="panel"><div className="panel-head"><h3>Simulate a UPI transfer</h3><span className="tag">TEST ENVIRONMENT</span></div><form onSubmit={analyze} className="payment-form"><label>Recipient UPI ID<input required value={form.recipient_upi} onChange={e=>setForm({...form,recipient_upi:e.target.value})}/></label><div className="fields"><label>Amount (₹)<input required type="number" min="1" value={form.amount} onChange={e=>setForm({...form,amount:e.target.value})}/></label><label>Typical payment (₹)<input required type="number" min="1" value={form.typical_amount} onChange={e=>setForm({...form,typical_amount:e.target.value})}/></label></div><div className="fields"><label>Payments in last hour<input type="number" min="0" max="100" value={form.recent_count} onChange={e=>setForm({...form,recent_count:e.target.value})}/></label><label>Transaction hour (0–23)<input type="number" min="0" max="23" value={form.hour} onChange={e=>setForm({...form,hour:e.target.value})}/></label></div><label className="check"><input type="checkbox" checked={form.new_recipient} onChange={e=>setForm({...form,new_recipient:e.target.checked})}/> New recipient (no previous payment history)</label><button className="primary full" disabled={loading}>{loading?'Analyzing…':'Analyze transaction risk →'}</button><p className="fine">This transaction is simulated. No bank is contacted and no money moves.</p></form></section><section className="panel result"><div className="panel-head"><h3>Risk assessment</h3><ShieldAlert size={20}/></div>{result?<><div className={'risk '+result.risk.toLowerCase()}><span>DETECTED RISK</span><strong>{result.score}<small>/100</small></strong><b>{result.risk} RISK</b></div><div className="decision">Decision: <b>{result.decision.replaceAll('_',' ')}</b></div><h4>Why was it flagged?</h4>{result.reasons.length?result.reasons.map((r,i)=><div className="reason" key={i}><AlertTriangle size={16}/>{r}</div>):<div className="reason"><CheckCircle2 size={16}/>No baseline risk indicators triggered</div>}<p className="fine">Rule-based baseline, not a calibrated fraud probability.</p>{mlResult&&<div className="research-warning"><BrainCircuit size={20}/><div><b>Experimental ML comparison</b><p>Estimated probability of a synthetic fraud label: {(mlResult.estimated_synthetic_label_probability*100).toFixed(1)}% · Research flag: {mlResult.research_flag?"YES":"NO"} (threshold 15%).</p><p>{mlResult.warning}</p></div></div>}</>:<div className="empty"><ShieldCheck size={54}/><h3>Ready to analyze</h3><p>Submit a simulated UPI transfer to see its risk score and explanation.</p></div>}</section></div>}
 {page==='qr'&&<div className="two-col"><section className="panel"><div className="panel-head"><h3>Inspect UPI payment URI</h3><ScanLine size={20}/></div><p className="fine">Paste the text decoded from a QR code. This checks URI syntax only; it cannot verify a real bank account or payee.</p><form className="payment-form" onSubmit={async e=>{e.preventDefault();try{const r=await fetch(API+'/api/qr/inspect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uri:qr})});const x=await r.json();setQrResult(r.ok?x:{error:JSON.stringify(x.detail)})}catch{setQrResult({error:'Backend offline'})}}}><label>UPI URI<textarea rows="5" value={qr} onChange={e=>setQr(e.target.value)} /></label><button className="primary">Inspect payment details</button></form></section><section className="panel"><h3>Inspection result</h3>{qrResult?<pre className="json-box">{JSON.stringify(qrResult,null,2)}</pre>:<div className="empty"><ScanLine size={48}/><p>Paste a UPI payment URI to inspect it.</p></div>}</section></div>}
 {page==='qr'&&<section className="panel qr-upload-panel"><QRImagePanel API={API} setQr={setQr} setQrResult={setQrResult}/></section>}
 {page==='model'&&<section className="panel"><div className="panel-head"><h3>Original dataset · Random Forest evaluation</h3><span className="tag">SYNTHETIC DATA ONLY</span></div>{metrics?<><div className="metrics model-metrics">{[['Precision',metrics.precision],['Recall',metrics.recall],['F1 Score',metrics.f1],['PR-AUC',metrics.pr_auc]].map(([k,v])=><div className="metric" key={k}><span>{k}</span><strong>{(v*100).toFixed(1)}%</strong></div>)}</div><p className="fine">{metrics.train_rows.toLocaleString()} training records · {metrics.test_rows.toLocaleString()} held-out records · 50% synthetic fraud prevalence.</p><div className="research-warning"><AlertTriangle size={20}/><div><b>Important research limitation</b><p>The original dataset is synthetic and its labels appear highly predictable. Perfect test metrics here do NOT demonstrate real UPI fraud detection capability. The live simulator deliberately uses transparent rules because its input features do not match the 20-feature training dataset.</p></div></div>{sandboxMetrics&&<><h4>New simulator-aligned research model</h4><div className="metrics model-metrics">{[['Precision',sandboxMetrics.precision],['Recall',sandboxMetrics.recall],['F1',sandboxMetrics.f1],['PR-AUC',sandboxMetrics.pr_auc]].map(([k,v])=><div className="metric" key={k}><span>{k}</span><strong>{(v*100).toFixed(1)}%</strong></div>)}</div><p className="fine">{sandboxMetrics.warning} Research threshold: {(sandboxMetrics.threshold*100).toFixed(0)}%. This model is compared with, not substituted for, the payment rule engine.</p></>}<h4>Confusion matrix</h4><div className="matrix"><div>True negatives<br/><b>{metrics.confusion_matrix[0][0]}</b></div><div>False positives<br/><b>{metrics.confusion_matrix[0][1]}</b></div><div>False negatives<br/><b>{metrics.confusion_matrix[1][0]}</b></div><div>True positives<br/><b>{metrics.confusion_matrix[1][1]}</b></div></div></>:<p>Run <code>python ml/train.py</code> to generate evaluation results.</p>}</section>}
 {page==='analytics'&&<section className="panel"><div className="panel-head"><h3>Fraud analytics · simulated transactions</h3><span className="tag">RULE-BASED SANDBOX</span></div>{analytics?<><div className="metrics model-metrics"><div className="metric"><span>Transactions</span><strong>{analytics.total}</strong></div><div className="metric"><span>Simulated volume</span><strong>₹{analytics.total_volume.toLocaleString('en-IN')}</strong></div><div className="metric"><span>Average risk score</span><strong>{analytics.average_risk_score}/100</strong></div><div className="metric"><span>Open cases</span><strong>{analytics.review_open}</strong></div></div><h4>Risk distribution</h4>{['HIGH','MEDIUM','LOW'].map(k=><div className="analytics-row" key={k}><span>{k} ({analytics.risk_distribution[k]})</span><div className="analytics-track"><div className={'analytics-fill '+k.toLowerCase()} style={{width:`${analytics.total?analytics.risk_distribution[k]/analytics.total*100:0}%`}}/></div></div>)}<h4>Daily transaction activity (last 30 active dates)</h4>{analytics.daily.length?<div className="analytics-bars">{analytics.daily.map(d=><div className="analytics-bar-cell" key={d.date} title={`${d.date}: ${d.total} transactions, ${d.high} high-risk`}><div className="analytics-bar" style={{height:`${Math.max(4,d.total/Math.max(...analytics.daily.map(x=>x.total))*100)}%`}}/><small>{d.date.slice(5)}</small></div>)}</div>:<p className="fine">No simulated transactions yet. Create some in UPI Sandbox.</p>}<p className="fine">{analytics.note} Charts are descriptive and do not establish real fraud detection accuracy.</p></>:<p>Loading analytics…</p>}</section>}
 {page==='reports'&&<section className="panel reports-panel"><div className="panel-head"><div><h3>Sandbox transaction reports</h3><p className="fine">Export transaction records for academic assessment and case review</p></div><span className="tag">ADMIN-RESTRICTED EXPORT</span></div><div className="report-summary"><div><Wallet size={22}/><span>Total simulated volume</span><b>₹{Number(analytics?.total_volume||0).toLocaleString('en-IN')}</b></div><div><ShieldAlert size={22}/><span>High-risk cases</span><b>{high}</b></div><div><TrendingUp size={22}/><span>Average rules risk</span><b>{analytics?.average_risk_score??0}/100</b></div></div><h4>Export CSV</h4><button className="primary" disabled={session?.user?.role!=='admin'} onClick={async()=>{try{const r=await fetch(API+'/api/reports/transactions.csv',{headers:{Authorization:'Bearer '+session.access_token}});if(!r.ok)throw Error('Export failed: '+r.status);const u=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=u;a.download='fraudshield_v7.csv';a.click();URL.revokeObjectURL(u)}catch(e){setReportError(e.message)}}}>Export with administrator login</button><p className="fine">{session?.user?.role==='admin'?'Authenticated admin export enabled':'Sign in as administrator from Security & Login to enable authenticated export.'}</p><p className="fine">Administrator login is required to download transaction records. Case review and export permissions are enforced by the backend.</p>{reportError&&<div className="error">{reportError}</div>}<div className="report-disclaimer"><Shield size={20}/><p>Research prototype: all exports contain simulated transactions and risk estimates. No bank integrations or money movement. Synthetic fraud labels are not proof of real-world fraud detection accuracy.</p></div></section>}
 {page==='copilot'&&<AICopilot API={API} session={session} transactions={transactions}/>}
 {page==='security'&&<FirebaseSecurity session={session} authStatus={authStatus} authError={authError}/>}
 {page==='investigation'&&<CaseManager API={API} session={session} cases={cases} refreshCases={()=>fetch(API+'/api/cases').then(r=>r.json()).then(setCases)}/>}
 {page==='model'&&<ComparisonPanel API={API}/>}
 {page==='model'&&<ExplainPanel API={API} session={session} form={form}/>}
 {page==='transactions'&&<section className="panel"><div className="panel-head"><h3>Transaction history</h3><div className="search"><Search size={16}/><input placeholder="Search recipient or ID" value={search} onChange={e=>setSearch(e.target.value)}/></div></div><div className="filter-pills">{['ALL','HIGH','MEDIUM','LOW'].map(r=><button key={r} className={riskFilter===r?'selected':''} onClick={()=>setRiskFilter(r)}>{r==='ALL'?'All transactions':r+' risk'}</button>)}</div><TransactionTable items={transactions.filter(x=>(x.recipient_upi+x.id).toLowerCase().includes(search.toLowerCase())&&(riskFilter==='ALL'||x.risk===riskFilter))}/></section>}
 <footer>FraudShield AI v10 • Academic research prototype • Synthetic transactions only • Live simulator uses transparent rules, not the research ML model</footer></main></div>
}
function TransactionTable({items}){return <div className="table-wrap"><table><thead><tr><th>TRANSACTION</th><th>RECIPIENT</th><th>AMOUNT</th><th>RISK SCORE</th><th>STATUS</th></tr></thead><tbody>{items.length?items.map(x=><tr key={x.id}><td><b>#{x.id.slice(0,8).toUpperCase()}</b><small>{new Date(x.timestamp).toLocaleString()}</small></td><td>{x.recipient_upi}</td><td>₹{x.amount.toLocaleString('en-IN')}</td><td>{x.score}/100</td><td><span className={'status '+x.risk.toLowerCase()}>{x.risk}</span></td></tr>):<tr><td colSpan="5" className="empty-row">No transactions yet. Start with the UPI sandbox.</td></tr>}</tbody></table></div>}

function RiskDonut({high,medium,low}){const total=high+medium+low;const h=total?high/total*100:0,m=total?medium/total*100:0;return <div className="donut-layout"><div className="donut" style={{background:total?`conic-gradient(#ff6588 0% ${h}%, #ffbf69 ${h}% ${h+m}%, #3e83ff ${h+m}% 100%)`:'conic-gradient(#283a5c 0 100%)'}}><div className="donut-center"><strong>{total.toLocaleString('en-IN')}</strong><small>transactions</small></div></div><div className="donut-legend">{[['High risk',high,'#ff6588'],['Medium risk',medium,'#ffbf69'],['Low risk',low,'#3e83ff']].map(([label,count,color])=><div key={label}><span className="legend-color" style={{background:color}}/>{label}<b>{total?(count/total*100).toFixed(1):'0.0'}%</b></div>)}</div></div>}
function RiskTrend({daily}){const rows=daily.slice(-7);const max=Math.max(1,...rows.map(x=>x.total));return rows.length?<div className="trend-chart">{rows.map(d=><div className="trend-day" key={d.date} title={`${d.date}: ${d.total} transactions`}><div className="trend-stack" style={{height:`${Math.max(7,d.total/max*100)}%`}}>{d.high>0&&<div className="trend-high" style={{flex:d.high}}/>}{d.medium>0&&<div className="trend-medium" style={{flex:d.medium}}/>}{d.low>0&&<div className="trend-low" style={{flex:d.low}}/>}</div><small>{d.date.slice(5)}</small></div>)}</div>:<div className="trend-empty"><BarChart3 size={36}/><span>Run a few simulated payments to populate the risk trend.</span></div>}
