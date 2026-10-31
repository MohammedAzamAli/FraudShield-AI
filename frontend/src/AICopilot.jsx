import React,{useState,useEffect} from 'react';
import {Bot,ImageUp,FileText,ShieldAlert,Send,Download} from 'lucide-react';

async function request(API,route,token,payload){
 const response=await fetch(API+route,{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},body:JSON.stringify(payload)});
 const data=await response.json().catch(()=>({detail:'Invalid response from server'}));
 if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:`Request failed (${response.status})`);
 return data;
}
export default function AICopilot({API,session,transactions}){
 const [tab,setTab]=useState('ask'),[provider,setProvider]=useState('openai'),[language,setLanguage]=useState('English');
 const [question,setQuestion]=useState('Explain the strongest risk indicators and what an investigator should check next.');
 const [transaction,setTransaction]=useState(''),[notes,setNotes]=useState(''),[image,setImage]=useState(null);
 const [result,setResult]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[status,setStatus]=useState(null);
 const permitted=session?.user?.role==='admin'||session?.user?.role==='analyst';
 useEffect(()=>{if(!permitted){setStatus(null);return;}let stopped=false;(async()=>{try{const r=await fetch(API+'/api/ai/status',{headers:{Authorization:`Bearer ${session.access_token}`}});if(r.ok&&!stopped)setStatus(await r.json());}catch{}})();return()=>{stopped=true}},[API,session?.access_token,permitted]);
 async function readImage(file){if(!file)return;setError('');setImage(null);if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>3*1024*1024){setError('Select a PNG, JPEG or WebP image up to 3 MB.');return;}
 const reader=new FileReader();reader.onload=()=>setImage({mime_type:file.type,image_base64:String(reader.result).split(',')[1],name:file.name});reader.onerror=()=>setError('Unable to read image');reader.readAsDataURL(file)}
 async function run(e){e.preventDefault();setError('');setResult('');setBusy(true);try{
 let route,payload;
 if(tab==='ask'){route='/api/ai/ask';payload={question,provider,language,transaction_id:transaction||null}}
 else if(tab==='screenshot'){if(!image)throw Error('Choose an image first.');route='/api/ai/screenshot';payload={mime_type:image.mime_type,image_base64:image.image_base64,description:notes}}
 else{if(!transaction)throw Error('Select a simulated transaction first.');route='/api/ai/report';payload={transaction_id:transaction,analyst_notes:notes,provider}}
 const data=await request(API,route,session.access_token,payload);setResult(data.answer||data.analysis||data.report_markdown||'No text returned');
 }catch(err){setError(err.message)}finally{setBusy(false)}}
 function save(){const blob=new Blob([`FraudShield AI v10 — ${tab}\nSYNTHETIC SANDBOX ONLY\n\n${result}`],{type:'text/plain'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`fraudshield-${tab}-draft.txt`;a.click();URL.revokeObjectURL(url)}
 return <section className="panel ai-workbench">
  <div className="panel-head"><div><h3><Bot size={21}/> AI Fraud Investigation Copilot</h3><p className="fine">Analyst-only assistant · third-party providers · synthetic or redacted data only</p></div><span className="tag">ADVISORY — HUMAN REVIEW</span></div>
  {!permitted?<div className="research-warning"><ShieldAlert size={20}/><div><b>Authentication required</b><p>Sign in as an analyst or administrator to access third-party AI tools. Viewers cannot transmit investigation data.</p></div></div>:<>
  <div className="filter-pills">{[['ask','Fraud Copilot'],['screenshot','Gemini Image Analysis'],['report','Case Report']].map(([id,label])=><button key={id} className={tab===id?'selected':''} onClick={()=>{setTab(id);setResult('');setError('');if(id==='screenshot')setProvider('gemini')}}>{label}</button>)}</div>
  <div className="ai-columns"><form className="payment-form" onSubmit={run}>
    {tab!=='screenshot'&&<label>AI provider<select value={provider} onChange={e=>setProvider(e.target.value)}>{['openai','gemini','groq'].map(p=><option key={p} value={p}>{p.toUpperCase()} {status?.configured?.[p]?'✓ key configured':''}</option>)}</select></label>}
    {tab!=='screenshot'&&<label>Simulated transaction<select value={transaction} onChange={e=>setTransaction(e.target.value)}><option value="">{tab==='report'?'Choose a transaction':'General guidance (no transaction)'}</option>{transactions.slice(0,100).map(t=><option key={t.id} value={t.id}>#{t.id.slice(0,8)} · ₹{t.amount.toLocaleString('en-IN')} · {t.risk}</option>)}</select></label>}
    {tab==='ask'&&<><label>Response language<select value={language} onChange={e=>setLanguage(e.target.value)}>{['English','Hindi','Telugu'].map(l=><option key={l}>{l}</option>)}</select></label><label>Investigation question<textarea rows={5} required maxLength={1200} value={question} onChange={e=>setQuestion(e.target.value)}/></label></>}
    {tab==='screenshot'&&<><label>Upload redacted screenshot<input type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>readImage(e.target.files?.[0])}/></label><p className="fine">{image?.name||'Images ≤3 MB; remove real names, UPI IDs, phone numbers, OTPs and QR secrets before upload.'}</p></>}
    {tab!=='ask'&&<label>{tab==='report'?'Investigation notes':'Optional screenshot context'}<textarea rows={4} maxLength={tab==='report'?1500:450} value={notes} onChange={e=>setNotes(e.target.value)} placeholder="Use synthetic or redacted information only"/></label>}
    <button className="primary" disabled={busy||!permitted}><Send size={16}/>{busy?'Contacting provider…':tab==='ask'?'Ask Copilot':tab==='screenshot'?'Analyze screenshot':'Draft investigation report'}</button>
  </form><div className="ai-response"><h4>{tab==='ask'?'AI assessment':tab==='screenshot'?'Screenshot observations':'Draft report'}</h4>{error&&<p className="error">{error}</p>}{result?<><div className="ai-result">{result}</div><button className="outline-btn" type="button" onClick={save}><Download size={16}/> Download draft</button></>:<div className="empty"><FileText size={40}/><p>AI output will appear here. Results are advisory and may contain errors.</p></div>}</div></div>
  <div className="research-warning"><ShieldAlert size={20}/><div><b>Privacy and research limitations</b><p>Sending a request transmits your entered text (and chosen image) to the selected external AI provider. Transaction context excludes raw UPI IDs. Never upload genuine personal or banking information without explicit consent. No AI action modifies a fraud verdict or closes a case.</p></div></div>
  </>}
 </section>
}
