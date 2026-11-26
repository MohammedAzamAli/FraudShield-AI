import React,{useMemo,useState} from 'react';
import {Activity,ChevronLeft,ChevronRight,Search,SlidersHorizontal} from 'lucide-react';

const pageSize=12;
const value=(row,key,fallback='')=>row?.[key]??row?.input_context?.[key]??fallback;

export default function TransactionHistory({transactions=[]}){
 const [search,setSearch]=useState(''),[riskFilter,setRiskFilter]=useState('ALL'),[flowFilter,setFlowFilter]=useState('ALL'),[categoryFilter,setCategoryFilter]=useState('ALL'),[stateFilter,setStateFilter]=useState('ALL'),[page,setPage]=useState(0);
 const flows=useMemo(()=>[...new Set(transactions.map(tx=>value(tx,'channel',value(tx,'upi_flow'))).filter(Boolean))].sort(),[transactions]);
 const categories=useMemo(()=>[...new Set(transactions.map(tx=>value(tx,'merchant_category')).filter(v=>v&&v!=='Unspecified'))].sort(),[transactions]);
 const states=useMemo(()=>[...new Set(transactions.map(tx=>value(tx,'transaction_state')).filter(v=>v&&v!=='Unspecified'))].sort(),[transactions]);
 const filtered=useMemo(()=>transactions.filter(tx=>{
  const risk=tx.risk||tx.risk_tier||'LOW';
  const flow=value(tx,'channel',value(tx,'upi_flow'));
  const category=value(tx,'merchant_category');
  const state=value(tx,'transaction_state');
  const searchText=[tx.id,tx.sender_upi,tx.recipient_upi,flow,category,state,value(tx,'payment_service_provider')].join(' ').toLowerCase();
  return (!search||searchText.includes(search.trim().toLowerCase()))
   &&(riskFilter==='ALL'||risk===riskFilter)
   &&(flowFilter==='ALL'||flow===flowFilter)
   &&(categoryFilter==='ALL'||category===categoryFilter)
   &&(stateFilter==='ALL'||state===stateFilter);
 }),[transactions,search,riskFilter,flowFilter,categoryFilter,stateFilter]);
 const loadedVolume=transactions.reduce((sum,tx)=>sum+Number(tx.amount||0),0);
 const avgRisk=transactions.length?transactions.reduce((sum,tx)=>sum+Number(tx.score??tx.risk_score??0),0)/transactions.length:0;
 const highCount=transactions.filter(tx=>['HIGH','CRITICAL'].includes(tx.risk||tx.risk_tier)).length;
 const pageCount=Math.max(1,Math.ceil(filtered.length/pageSize));
 const visible=filtered.slice(page*pageSize,(page+1)*pageSize);
 const resetPage=setter=>value=>{setter(value);setPage(0)};

 return <section className="panel transaction-history-panel">
  <div className="panel-head"><div><h3><Activity size={19}/> Transaction history</h3><p className="fine">Search and filter recent sandbox transactions with the UPI context recorded at scoring time.</p></div><span className="tag">LATEST {transactions.length} LOADED</span></div>
  <div className="history-summary-grid"><div><span>Loaded records</span><b>{transactions.length.toLocaleString()}</b></div><div><span>High / critical</span><b className="history-high-value">{highCount.toLocaleString()}</b></div><div><span>Simulated volume</span><b>₹{loadedVolume.toLocaleString('en-IN',{maximumFractionDigits:0})}</b></div><div><span>Average risk score</span><b>{avgRisk.toFixed(1)} / 100</b></div></div>
  <div className="transaction-history-controls">
   <label className="history-search"><Search size={16}/><input aria-label="Search transactions" placeholder="Search ID, sender, recipient, flow…" value={search} onChange={event=>resetPage(setSearch)(event.target.value)}/></label>
   <label><span>Risk tier</span><select value={riskFilter} onChange={event=>resetPage(setRiskFilter)(event.target.value)}><option value="ALL">All risk tiers</option><option value="CRITICAL">Critical</option><option value="HIGH">High</option><option value="MEDIUM">Medium</option><option value="LOW">Low</option></select></label>
   <label><span>UPI flow</span><select value={flowFilter} onChange={event=>resetPage(setFlowFilter)(event.target.value)}><option value="ALL">All flows</option>{flows.map(flow=><option value={flow} key={flow}>{flow.replaceAll('_',' ')}</option>)}</select></label>
   <label><span>Merchant category</span><select value={categoryFilter} onChange={event=>resetPage(setCategoryFilter)(event.target.value)}><option value="ALL">All categories</option>{categories.map(category=><option key={category}>{category}</option>)}</select></label>
   <label><span>State</span><select value={stateFilter} onChange={event=>resetPage(setStateFilter)(event.target.value)}><option value="ALL">All states</option>{states.map(state=><option key={state}>{state}</option>)}</select></label>
   <button className="history-reset" onClick={()=>{setSearch('');setRiskFilter('ALL');setFlowFilter('ALL');setCategoryFilter('ALL');setStateFilter('ALL');setPage(0)}}><SlidersHorizontal size={15}/> Reset</button>
  </div>
  <div className="table-wrap"><table className="history-context-table"><thead><tr><th>TRANSACTION</th><th>PARTIES</th><th>AMOUNT</th><th>PAYMENT CONTEXT</th><th>RISK</th><th>STATUS</th></tr></thead><tbody>{visible.length?visible.map(tx=>{
   const risk=tx.risk||tx.risk_tier||'LOW';
   const flow=value(tx,'channel',value(tx,'upi_flow','Unknown flow'));
   const timestamp=tx.timestamp?new Date(tx.timestamp).toLocaleString():'';
   const txTime=value(tx,'transaction_time',tx.hour!==undefined?`${String(tx.hour).padStart(2,'0')}:00`:'—');
   const newDevice=Boolean(value(tx,'device_is_new',value(tx,'new_device',false)));
   const vpn=Boolean(value(tx,'vpn_detected',value(tx,'vpn_ip',false)));
   return <tr key={tx.id}><td><b>#{String(tx.id||'').slice(0,8).toUpperCase()}</b><small>{timestamp}</small></td><td><b>{tx.recipient_upi||'—'}</b><small>From {tx.sender_upi||'simulated sender'}</small></td><td>₹{Number(tx.amount||0).toLocaleString('en-IN',{maximumFractionDigits:2})}</td><td><div className="history-context-main">{flow.replaceAll('_',' ')} · {value(tx,'payment_service_provider','Provider n/a')}</div><small>{value(tx,'merchant_category','Category n/a')} · {value(tx,'transaction_state','State n/a')} · {value(tx,'device_os','OS n/a')} · {txTime}</small><small>{value(tx,'transactions_last_24h','—')} in 24h · 30-day avg ₹{Number(value(tx,'average_amount_30d',tx.typical_amount||0)).toLocaleString('en-IN',{maximumFractionDigits:0})}{newDevice?' · New device':''}{vpn?' · VPN':''}</small></td><td><b>{Number(tx.score??tx.risk_score??0)}/100</b></td><td><span className={'status '+risk.toLowerCase()}>{risk}</span></td></tr>
  }):<tr><td colSpan={6} className="empty-row">{transactions.length?'No transactions match these filters.':'No transactions have been scored yet. Use UPI Sandbox to create a simulated transaction.'}</td></tr>}</tbody></table></div>
  <div className="history-pagination"><span>{filtered.length?`${(page*pageSize+1).toLocaleString()}–${Math.min((page+1)*pageSize,filtered.length).toLocaleString()} of ${filtered.length.toLocaleString()} matching`:'0 matching records'}</span><div><button className="outline-btn" disabled={page===0} onClick={()=>setPage(current=>Math.max(0,current-1))}><ChevronLeft size={16}/> Previous</button><span>Page {filtered.length?page+1:0} / {filtered.length?pageCount:0}</span><button className="outline-btn" disabled={page+1>=pageCount} onClick={()=>setPage(current=>Math.min(pageCount-1,current+1))}>Next <ChevronRight size={16}/></button></div></div>
 </section>;
}
