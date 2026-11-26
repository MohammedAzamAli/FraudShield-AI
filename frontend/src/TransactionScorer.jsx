import React,{useMemo,useState} from 'react';
import {Activity,AlertTriangle,CheckCircle2,Send,ShieldAlert,ShieldCheck} from 'lucide-react';

const states=['Andhra Pradesh','Arunachal Pradesh','Assam','Bihar','Chhattisgarh','Goa','Gujarat','Haryana','Himachal Pradesh','Jharkhand','Karnataka','Kerala','Madhya Pradesh','Maharashtra','Manipur','Meghalaya','Mizoram','Nagaland','Odisha','Punjab','Rajasthan','Sikkim','Tamil Nadu','Telangana','Tripura','Uttar Pradesh','Uttarakhand','West Bengal','Delhi','Jammu and Kashmir','Ladakh','Puducherry'];
const providers=['PhonePe','Google Pay','Paytm','BHIM','Amazon Pay','Other'];
const flows=[['UPI_P2P','P2P transfer'],['UPI_P2M','P2M payment'],['COLLECT_REQUEST','P2M collect request'],['QR_CODE','QR payment']];
const categories=['General','Groceries','Utilities','Food and dining','Travel','Retail','Donations','Money Mule Account','Phishing Collect','Other'];
const modes=[
 {id:'high',label:'High sensitivity',short:'High',cutoff:0.15,description:'Flags more transactions for review.'},
 {id:'balanced',label:'Balanced',short:'Balanced',cutoff:0.25,description:'Default research screening level.'},
 {id:'low',label:'Low noise',short:'Low',cutoff:0.45,description:'Flags fewer transactions for review.'}
];

function localTime(){const now=new Date();return `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;}

function ProbabilityGauge({probability}){
 const value=probability===null?0:Math.max(0,Math.min(1,probability));
 const angle=Math.PI*(1-value),pointerX=150+102*Math.cos(angle),pointerY=150-102*Math.sin(angle);
 return <svg className="transaction-gauge" viewBox="0 0 300 178" role="img" aria-label={probability===null?'Sandbox fraud probability unavailable':`Sandbox model probability ${(value*100).toFixed(1)} percent`}>
  <defs><linearGradient id="transactionGaugeGradient" x1="0" x2="1"><stop offset="0%" stopColor="#46d7aa"/><stop offset="52%" stopColor="#ffc366"/><stop offset="100%" stopColor="#ff6588"/></linearGradient></defs>
  <path d="M 24 150 A 126 126 0 0 1 276 150" pathLength="100" className="transaction-gauge-track"/>
  {probability!==null&&<path d="M 24 150 A 126 126 0 0 1 276 150" pathLength="100" strokeDasharray={`${value*100} 100`} className="transaction-gauge-progress"/>}
  {probability!==null&&<><line x1="150" y1="150" x2={pointerX} y2={pointerY} className="transaction-gauge-needle"/><circle cx="150" cy="150" r="7" className="transaction-gauge-hub"/></>}
  <text x="150" y="128" textAnchor="middle" className="transaction-gauge-value">{probability===null?'—':`${(value*100).toFixed(1)}%`}</text>
  <text x="22" y="172" className="transaction-gauge-label">0%</text><text x="263" y="172" className="transaction-gauge-label">100%</text>
 </svg>;
}

export default function TransactionScorer({API,onScored}){
 const [form,setForm]=useState({amount:'440',transactions_last_24h:'1',average_amount_30d:'800',new_device:true,first_merchant_visit:true,vpn_ip:false,payment_service_provider:'Amazon Pay',channel:'COLLECT_REQUEST',merchant_category:'Donations',transaction_state:'Delhi',device_os:'Android',transaction_time:localTime(),recipient_upi:'demo.merchant@upi'});
 const [screeningMode,setScreeningMode]=useState('balanced'),[cutoff,setCutoff]=useState(0.25);
 const [result,setResult]=useState(null),[modelResult,setModelResult]=useState(null),[modelError,setModelError]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const probability=useMemo(()=>{
  const value=modelResult?.estimated_synthetic_label_probability;
  if(value===null||value===undefined||value==='')return null;
  return Number.isFinite(Number(value))?Math.max(0,Math.min(1,Number(value))):null;
 },[modelResult]);
 const researchFlag=probability!==null&&probability>=cutoff;
 const update=(key,value)=>setForm(previous=>({...previous,[key]:value}));
 const changeMode=mode=>{setScreeningMode(mode.id);setCutoff(mode.cutoff);};
 const changeCutoff=value=>{
  const next=Number(value);setCutoff(next);
  setScreeningMode(modes.find(mode=>mode.cutoff===next)?.id||'custom');
 };

 async function scoreTransaction(event){
  event.preventDefault();setBusy(true);setError('');setModelError('');setResult(null);setModelResult(null);
  const hour=Number((form.transaction_time||'12:00').split(':')[0]);
  const payload={
   amount:Number(form.amount),recipient_upi:form.recipient_upi||'demo.merchant@upi',sender_upi:'rahul.sharma@okaxis',
   typical_amount:Number(form.average_amount_30d),recent_count:1,hour,
   new_recipient:form.first_merchant_visit,first_merchant_visit:form.first_merchant_visit,
   device_is_new:form.new_device,vpn_detected:form.vpn_ip,channel:form.channel,
   transactions_last_24h:Number(form.transactions_last_24h),payment_service_provider:form.payment_service_provider,
   merchant_category:form.merchant_category,transaction_state:form.transaction_state,device_os:form.device_os,
   transaction_time:form.transaction_time,screening_mode:screeningMode,screening_cutoff:cutoff
  };
  try{
   const response=await fetch(API+'/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
   const data=await response.json().catch(()=>({detail:'Invalid response from server'}));
   if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail||`Scoring failed (${response.status})`));
   setResult(data);
   try{
    const modelResponse=await fetch(API+'/api/ml/sandbox-predict',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const modelData=await modelResponse.json().catch(()=>({}));
    if(modelResponse.ok)setModelResult(modelData);else setModelError('The sandbox model estimate is unavailable for this transaction.');
   }catch{setModelError('The sandbox model estimate is unavailable for this transaction.');}
   if(onScored)await onScored();
  }catch(err){setError(err.message||'Unable to score this transaction.');}
  finally{setBusy(false);}
 }

 return <section className="panel transaction-scoring-panel">
  <div className="panel-head"><div><h3><Activity size={19}/> Score a single transaction</h3><p className="fine">Enter simulated payment context to compare the risk engine and sandbox model.</p></div><span className="tag">SIMULATED SCORING</span></div>
  <div className="transaction-scoring-layout">
   <form className="transaction-scoring-form" onSubmit={scoreTransaction}>
    <div className="transaction-input-grid three">
     <label>Amount (₹)<input required type="number" min="1" step="0.01" value={form.amount} onChange={e=>update('amount',e.target.value)}/></label>
     <label>Transactions last 24 hr<input required type="number" min="0" max="500" value={form.transactions_last_24h} onChange={e=>update('transactions_last_24h',e.target.value)}/></label>
     <label>30-day average (₹)<input required type="number" min="1" step="0.01" value={form.average_amount_30d} onChange={e=>update('average_amount_30d',e.target.value)}/></label>
    </div>
    <div className="transaction-check-grid">
     <label><input type="checkbox" checked={form.new_device} onChange={e=>update('new_device',e.target.checked)}/> New device</label>
     <label><input type="checkbox" checked={form.first_merchant_visit} onChange={e=>update('first_merchant_visit',e.target.checked)}/> First merchant visit</label>
     <label><input type="checkbox" checked={form.vpn_ip} onChange={e=>update('vpn_ip',e.target.checked)}/> VPN IP</label>
    </div>
    <div className="transaction-input-grid three">
     <label>PSP<select value={form.payment_service_provider} onChange={e=>update('payment_service_provider',e.target.value)}>{providers.map(option=><option key={option}>{option}</option>)}</select></label>
     <label>UPI flow<select value={form.channel} onChange={e=>update('channel',e.target.value)}>{flows.map(([value,label])=><option value={value} key={value}>{label}</option>)}</select></label>
     <label>Merchant category<select value={form.merchant_category} onChange={e=>update('merchant_category',e.target.value)}>{categories.map(option=><option key={option}>{option}</option>)}</select></label>
     <label>Transaction state<select value={form.transaction_state} onChange={e=>update('transaction_state',e.target.value)}>{states.map(option=><option key={option}>{option}</option>)}</select></label>
     <label>Device OS<select value={form.device_os} onChange={e=>update('device_os',e.target.value)}>{['Android','iOS','Web','Unknown'].map(option=><option key={option}>{option}</option>)}</select></label>
     <label>Time<input required type="time" value={form.transaction_time} onChange={e=>update('transaction_time',e.target.value)}/></label>
    </div>
    <label>Simulated recipient UPI<input required value={form.recipient_upi} onChange={e=>update('recipient_upi',e.target.value)} maxLength={120}/></label>
    <div className="screening-controls">
     <div className="screening-mode-head"><div><b>Screening mode</b><span>Choose how sensitive the research flag should be.</span></div><strong>{(cutoff*100).toFixed(0)}% cutoff</strong></div>
     <div className="screening-mode-buttons">{modes.map(mode=><button type="button" key={mode.id} className={screeningMode===mode.id?'selected':''} onClick={()=>changeMode(mode)} aria-pressed={screeningMode===mode.id}><b>{mode.short}</b><small>{(mode.cutoff*100).toFixed(0)}% cutoff</small></button>)}</div>
     <label className="screening-range">Probability cutoff<input type="range" min="0.05" max="0.80" step="0.01" value={cutoff} onChange={e=>changeCutoff(e.target.value)}/><span>{screeningMode==='custom'?'Custom':modes.find(mode=>mode.id===screeningMode)?.label} · {modes.find(mode=>mode.id===screeningMode)?.description||'Adjust the research threshold manually.'}</span></label>
    </div>
    <p className="transaction-data-note">The 24-hour count feeds a sandbox velocity rule (10+ is elevated; 20+ is high). PSP and device OS are saved as context only and do not increase risk by themselves. A state different from the simulated customer profile is treated as an unusual-location signal.</p>
    {error&&<p className="error">{error}</p>}
    <button className="primary full" disabled={busy}><Send size={16}/>{busy?'Scoring transaction…':'Score transaction'}</button>
    <p className="fine">This sandbox estimate is advisory. It does not contact a bank, verify a real payment, or prove fraud.</p>
   </form>
   <aside className="transaction-score-result">
    {!result?<div className="empty"><ShieldCheck size={46}/><h4>Ready to score</h4><p>Submit a simulated transaction to see its risk assessment and probability estimate.</p></div>:<>
     <div className="transaction-result-summary"><div><span>Risk engine score</span><strong className={result.risk?.toLowerCase()}>{result.score}<small>/100</small></strong></div><div><span>Decision</span><b>{result.decision?.replaceAll('_',' ')}</b></div><div><span>Risk tier</span><b className={'status '+result.risk?.toLowerCase()}>{result.risk}</b></div></div>
     <div className="transaction-gauge-card"><div><h4>Fraud probability</h4><span>Sandbox model estimate</span></div><ProbabilityGauge probability={probability}/><div className={'transaction-screening-result '+(probability===null?'unavailable':researchFlag?'flagged':'clear')}>
      {probability===null?<><AlertTriangle size={16}/><b>Model estimate unavailable</b></>:researchFlag?<><ShieldAlert size={16}/><b>Flag for review · {(probability*100).toFixed(1)}% ≥ {(cutoff*100).toFixed(0)}%</b></>:<><CheckCircle2 size={16}/><b>Below cutoff · {(probability*100).toFixed(1)}% &lt; {(cutoff*100).toFixed(0)}%</b></>}
     </div>{modelError&&<p className="fine">{modelError}</p>}<p className="fine">This probability estimates a synthetic training label; it is not calibrated to real-world fraud outcomes. The 24-hour count affects the separate velocity rule, and the cutoff only changes this research flag, not the risk engine decision.</p></div>
     <div className="transaction-reasons"><h4>Risk indicators</h4>{result.reasons?.length?result.reasons.map((reason,index)=><div className="reason" key={`${index}-${reason}`}><AlertTriangle size={15}/>{reason}</div>):<p className="fine">No risk indicators were returned.</p>}</div>
     <p className="transaction-id-note">Saved as simulated transaction #{String(result.id||'').slice(0,8).toUpperCase()}</p>
    </>}
   </aside>
  </div>
 </section>;
}
