import React,{useEffect,useRef,useState} from 'react';
import {Bot,Download,FileText,ImageUp,Plus,Send,ShieldAlert,Sparkles,UserRound} from 'lucide-react';

const starters=[
 'How does UPI fraud usually happen?',
 'What could make a transaction risky?',
 'How can I reduce payment risk?',
 'What should I do after a suspected scam?'
];
const transactionStarters=[
 'Why was this transaction flagged?',
 'Which signals raised its risk score?',
 'What should an investigator check next?',
 'What controls fit this transaction?'
];

async function request(API,route,token,payload){
 const response=await fetch(API+route,{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},body:JSON.stringify(payload)});
 const data=await response.json().catch(()=>({detail:'Invalid response from server'}));
 if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:`Request failed (${response.status})`);
 return data;
}

export default function AICopilot({API,session,transactions}){
 const [tab,setTab]=useState('chat'),[language,setLanguage]=useState('English');
 const [question,setQuestion]=useState(''),[transaction,setTransaction]=useState(''),[notes,setNotes]=useState(''),[image,setImage]=useState(null);
 const [messages,setMessages]=useState([]),[toolResult,setToolResult]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[status,setStatus]=useState(null);
 const bottomRef=useRef(null);
 const signedIn=Boolean(session?.access_token);
 const canInvestigate=['admin','analyst'].includes(session?.user?.role);
 const selectedTransaction=transactions.find(item=>String(item.id)===String(transaction));
 const visibleStarters=transaction?transactionStarters:starters;

 useEffect(()=>{
  if(!signedIn){setStatus(null);return;}
  let stopped=false;
  (async()=>{try{const response=await fetch(API+'/api/ai/status',{headers:{Authorization:`Bearer ${session.access_token}`}});if(response.ok&&!stopped)setStatus(await response.json());}catch{if(!stopped)setStatus({configured:null,mode:'unavailable'});}})();
  return()=>{stopped=true};
 },[API,session?.access_token,signedIn]);

 useEffect(()=>{bottomRef.current?.scrollIntoView({behavior:'smooth',block:'end'});},[messages,busy,tab]);

 async function readImage(file){
  if(!file)return;
  setError('');setImage(null);
  if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>3*1024*1024){setError('Choose a PNG, JPEG or WebP image up to 3 MB.');return;}
  const reader=new FileReader();
  reader.onload=()=>setImage({mime_type:file.type,image_base64:String(reader.result).split(',')[1],name:file.name});
  reader.onerror=()=>setError('Unable to read image.');
  reader.readAsDataURL(file);
 }

 async function sendChat(e){
  e.preventDefault();
  const currentQuestion=question.trim();
  if(currentQuestion.length<3){setError('Ask a question about payment fraud or transaction safety.');return;}
  setError('');setQuestion('');setBusy(true);
  const history=messages.slice(-12).map(({role,content})=>({role,content}));
  setMessages(previous=>[...previous,{role:'user',content:currentQuestion}]);
  try{
   const data=await request(API,'/api/ai/ask',session.access_token,{question:currentQuestion,history,language,transaction_id:canInvestigate?(transaction||null):null});
   setMessages(previous=>[...previous,{role:'assistant',content:data.answer||'Gemini did not return a response.'}]);
  }catch(err){setError(err.message);}
  finally{setBusy(false);}
 }

 async function runTool(e){
  e.preventDefault();setError('');setToolResult('');setBusy(true);
  try{
   let route,payload;
   if(tab==='image'){
    if(!image)throw Error('Choose a redacted screenshot first.');
    route='/api/ai/screenshot';payload={mime_type:image.mime_type,image_base64:image.image_base64,description:notes};
   }else{
    if(!transaction)throw Error('Select a simulated transaction first.');
    route='/api/ai/report';payload={transaction_id:transaction,analyst_notes:notes};
   }
   const data=await request(API,route,session.access_token,payload);
   setToolResult(data.analysis||data.report_markdown||'Gemini did not return a response.');
  }catch(err){setError(err.message);}
  finally{setBusy(false);}
 }

 function download(text,name){
  const blob=new Blob([`FraudShield AI · Gemini\nSynthetic sandbox advisory\n\n${text}`],{type:'text/plain'});
  const url=URL.createObjectURL(blob);const anchor=document.createElement('a');anchor.href=url;anchor.download=name;anchor.click();URL.revokeObjectURL(url);
 }

 function resetChat(){setMessages([]);setQuestion('');setError('');}
 function changeTransaction(nextTransaction){
  if(nextTransaction===transaction)return;
  setTransaction(nextTransaction);
  setMessages([]);
  setQuestion('');
  setError('');
  setToolResult('');
 }
 const tabs=canInvestigate?[['chat','Fraud chat'],['image','Screenshot review'],['report','Case report']]:[['chat','Fraud chat']];

 return <section className="panel ai-workbench">
  <div className="panel-head"><div><h3><Bot size={21}/> FraudShield AI Assistant</h3><p className="fine">Ask follow-up questions about payment fraud, risk signals, prevention, and safe next steps.</p></div><span className="tag">GOOGLE GEMINI · ADVISORY</span></div>
  {!signedIn?<div className="research-warning"><ShieldAlert size={20}/><div><b>Sign in to chat with Gemini</b><p>Any signed-in project user can ask general fraud-safety questions. Analyst tools require an analyst or administrator account.</p></div></div>:<>
   <div className="ai-provider-bar"><div className={'ai-provider-state '+(status?.configured===true?'ready':status?.configured===false?'missing':'')}><span/>{status?.configured===true?`Gemini configured · ${status.active_gemini_model}`:status?.configured===false?'Gemini API key required':'Checking Gemini configuration…'}</div><span className="fine">Only Google Gemini powers Copilot</span></div>
   {status?.configured===false&&<div className="research-warning"><ShieldAlert size={20}/><div><b>Gemini needs configuration</b><p>Add GEMINI_API_KEY to backend/.env and restart the backend.</p></div></div>}
   <div className="filter-pills ai-tabs">{tabs.map(([id,label])=><button key={id} className={tab===id?'selected':''} onClick={()=>{setTab(id);setError('');setToolResult('');}}>{label}</button>)}</div>
   {tab==='chat'?<>
    <div className="copilot-chat-layout">
     <aside className="copilot-chat-sidebar">
      <div><span className="chat-side-label">CHAT SETTINGS</span><label>Response language<select value={language} onChange={e=>setLanguage(e.target.value)}>{['English','Hindi','Telugu'].map(item=><option key={item}>{item}</option>)}</select></label></div>
      {canInvestigate&&<div className="chat-transaction-setting"><label>Transaction context<select value={transaction} onChange={e=>changeTransaction(e.target.value)}><option value="">General guidance (default)</option>{transactions.slice(0,100).map(item=><option key={item.id} value={item.id}>#{item.id.slice(0,8)} · ₹{item.amount.toLocaleString('en-IN')} · {item.risk}</option>)}</select></label><div className={'chat-mode-indicator '+(transaction?'transaction':'general')}><strong>{transaction?'TRANSACTION-SPECIFIC CHAT':'GENERAL GUIDANCE'}</strong><span>{transaction&&selectedTransaction?`Gemini will focus on #${selectedTransaction.id.slice(0,8)} · ₹${selectedTransaction.amount.toLocaleString('en-IN')} · ${selectedTransaction.risk}.`:'Select a transaction to ask about its risk signals and next steps.'}</span></div><p className="fine">Changing the selected transaction starts a fresh chat so earlier discussion cannot mix into this case.</p></div>}
      <div className="chat-starters"><span className="chat-side-label">{transaction?'ASK ABOUT THIS TRANSACTION':'TRY ASKING'}</span>{visibleStarters.map(item=><button type="button" key={item} onClick={()=>{setQuestion(item);setError('');}}>{item}</button>)}</div>
      <p className="fine">Chat uses up to the latest 12 messages for context. Avoid sharing real account details, phone numbers, PINs, or OTPs.</p>
     </aside>
     <div className="copilot-chat-main">
      <div className="copilot-messages" role="log" aria-live="polite" aria-label="Fraud guidance conversation">
       {!messages.length?<div className="chat-welcome"><div className="chat-welcome-icon"><Sparkles size={24}/></div><h4>What would you like to understand?</h4><p>Ask how scams work, why a simulated payment may look risky, or what steps can reduce the chance of fraud.</p></div>:messages.map((message,index)=><div className={'chat-message '+message.role} key={`${message.role}-${index}`}><div className="chat-avatar">{message.role==='assistant'?<Bot size={17}/>:<UserRound size={17}/>}</div><div className="chat-message-content"><span>{message.role==='assistant'?'Gemini':'You'}</span><p>{message.content}</p></div></div>)}
       {busy&&<div className="chat-message assistant"><div className="chat-avatar"><Bot size={17}/></div><div className="chat-message-content"><span>Gemini</span><p className="chat-thinking">Thinking through your question…</p></div></div>}
       <div ref={bottomRef}/>
      </div>
      {error&&<p className="error ai-chat-error">{error}</p>}
      <form className="copilot-composer" onSubmit={sendChat}>
       <textarea rows={2} required maxLength={1200} value={question} onChange={e=>setQuestion(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();e.currentTarget.form?.requestSubmit();}}} placeholder="Ask about payment fraud or transaction safety…" disabled={busy||status?.configured===false}/>
       <div className="composer-bottom"><span>{question.length}/1200 · Enter to send, Shift+Enter for a new line</span><div><button type="button" className="outline-btn" onClick={resetChat} disabled={!messages.length||busy}><Plus size={15}/> New chat</button><button className="primary" disabled={busy||!question.trim()||status?.configured===false}><Send size={16}/>{busy?'Gemini is replying…':'Send'}</button></div></div>
      </form>
     </div>
    </div>
    <div className="research-warning"><ShieldAlert size={20}/><div><b>Safety and privacy</b><p>Copilot provides general guidance, not a verified fraud verdict. Chat messages and optional simulated risk context are sent to Google Gemini. Transaction identifiers are omitted from that context; never enter real banking details.</p></div></div>
    {!!messages.length&&<div className="chat-export-row"><button className="outline-btn" type="button" onClick={()=>download(messages.map(item=>`${item.role==='user'?'You':'Gemini'}: ${item.content}`).join('\n\n'),'fraudshield-gemini-chat.txt')}><Download size={15}/> Download conversation</button></div>}
   </>:<div className="ai-tool-layout"><form className="payment-form" onSubmit={runTool}>
     {tab==='image'?<><label>Upload a redacted screenshot<input type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>readImage(e.target.files?.[0])}/></label><p className="fine">{image?.name||'PNG, JPEG or WebP up to 3 MB. Remove names, UPI IDs, phone numbers, OTPs, and QR secrets.'}</p></>:<label>Simulated transaction<select required value={transaction} onChange={e=>changeTransaction(e.target.value)}><option value="">Choose a transaction</option>{transactions.slice(0,100).map(item=><option key={item.id} value={item.id}>#{item.id.slice(0,8)} · ₹{item.amount.toLocaleString('en-IN')} · {item.risk}</option>)}</select></label>}
     <label>{tab==='report'?'Analyst notes':'Optional screenshot context'}<textarea rows={4} maxLength={tab==='report'?1500:450} value={notes} onChange={e=>setNotes(e.target.value)} placeholder="Use simulated or redacted information only"/></label>
     <button className="primary" disabled={busy||status?.configured===false}><Send size={16}/>{busy?'Gemini is working…':tab==='image'?'Review screenshot':'Draft case report'}</button>
    </form><div className="ai-response"><h4>{tab==='image'?<><ImageUp size={18}/> Screenshot observations</>:<><FileText size={18}/> Case report draft</>}</h4>{error&&<p className="error">{error}</p>}{toolResult?<><div className="ai-result">{toolResult}</div><button className="outline-btn" type="button" onClick={()=>download(toolResult,`fraudshield-gemini-${tab}.txt`)}><Download size={15}/> Download draft</button></>:<div className="empty"><FileText size={40}/><p>Gemini’s advisory response will appear here.</p></div>}</div></div>}
  </>}
 </section>
}
