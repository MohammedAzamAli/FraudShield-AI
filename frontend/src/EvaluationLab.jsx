import React,{useEffect,useState} from 'react';
import {BrainCircuit} from 'lucide-react';

const percent=value=>`${(Number(value||0)*100).toFixed(1)}%`;

export default function EvaluationLab({metrics}){
 const [threshold,setThreshold]=useState(Number(metrics?.threshold??0.5));
 useEffect(()=>setThreshold(Number(metrics?.threshold??0.5)),[metrics?.threshold]);

 if(!metrics)return <section className="panel evaluation-lab"><h3><BrainCircuit size={19}/> Evaluation diagnostics</h3><p className="fine">Loading the sandbox evaluation…</p></section>;
 if(!metrics.available)return <section className="panel evaluation-lab"><h3><BrainCircuit size={19}/> Evaluation diagnostics</h3><p className="fine">{metrics.message||'Sandbox evaluation details are unavailable.'}</p></section>;

 const sweep=metrics.threshold_sweep||[];
 const currentRow=sweep.reduce((closest,row)=>Math.abs(row.threshold-threshold)<Math.abs(closest.threshold-threshold)?row:closest,sweep[0]||{threshold:0.5});

 return <section className="panel evaluation-lab">
  <div className="panel-head"><div><h3><BrainCircuit size={19}/> Evaluation diagnostics</h3><p className="fine">ROC, precision–recall, and threshold views for the same generated sandbox test used in the 88.0% result above.</p></div><span className="tag">ONE EVALUATION · RANDOM FOREST</span></div>
  <div className="evaluation-chart-grid">
   <CurveCard title="ROC curve" subtitle="False positive rate vs. true positive rate" points={metrics.roc_curve} auc={metrics.roc_auc} kind="roc" color="#6fa6ff"/>
   <CurveCard title="Precision–recall curve" subtitle="Precision vs. recall on the held-out set" points={metrics.pr_curve} auc={metrics.pr_auc} kind="pr" color="#ff9b71" baseline={metrics.fraud_prevalence}/>
  </div>
  <section className="evaluation-block threshold-block"><div className="evaluation-block-head"><div><h4>Validation threshold sweep</h4><p>Explore the precision, recall, and F1 tradeoff on validation data. The score cards and confusion matrix above stay fixed at the held-out test threshold.</p></div></div>
   <ThresholdChart rows={sweep} selected={threshold}/>
   <div className="threshold-inspection"><label>Explore threshold <input type="range" min="0.05" max="0.95" step="0.01" value={threshold} onChange={event=>setThreshold(Number(event.target.value))}/><b>{threshold.toFixed(2)}</b></label><p className="fine">This validation-only slider shows where the threshold falls. It does not change the reported held-out result or UPI Sandbox decisions. At the nearest plotted point, {Number(currentRow.flagged_count||0).toLocaleString()} of {Number(metrics.validation_rows||0).toLocaleString()} validation examples are flagged.</p></div>
  </section>
 </section>;
}

function CurveCard({title,subtitle,points,auc,kind,color,baseline:prBaseline}){
 const left=42,top=12,width=280,height=178;
 const path=(points||[]).map(([x,y],index)=>`${index?'L':'M'} ${(left+Number(x)*width).toFixed(2)} ${(top+(1-Number(y))*height).toFixed(2)}`).join(' ');
 const baseline=kind==='roc'?`${left},${top+height} ${left+width},${top}`:`${left},${top+(1-Number(prBaseline||0))*height} ${left+width},${top+(1-Number(prBaseline||0))*height}`;
 return <section className="evaluation-block curve-card"><div className="evaluation-block-head"><div><h4>{title}</h4><p>{subtitle}</p></div><b>{kind==='roc'?'ROC-AUC':'PR-AUC'} {percent(auc)}</b></div><svg viewBox="0 0 340 232" role="img" aria-label={`${title}, ${percent(auc)}`}><g className="curve-grid">{[0,0.5,1].map(t=><React.Fragment key={t}><line x1={left} y1={top+(1-t)*height} x2={left+width} y2={top+(1-t)*height}/><line x1={left+t*width} y1={top} x2={left+t*width} y2={top+height}/></React.Fragment>)}</g><polyline points={baseline} className="curve-baseline"/><path d={path} fill="none" stroke={color} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round"/><line x1={left} y1={top+height} x2={left+width} y2={top+height} className="curve-axis"/><line x1={left} y1={top} x2={left} y2={top+height} className="curve-axis"/><text x={left} y="211">0</text><text x={left+width-8} y="211">1</text><text x="174" y="229" textAnchor="middle">{kind==='roc'?'False positive rate':'Recall'}</text><text x="12" y="107" transform="rotate(-90 12 107)" textAnchor="middle">{kind==='roc'?'True positive rate':'Precision'}</text></svg></section>;
}

function ThresholdChart({rows,selected}){
 const left=40,top=15,width=700,height=175;
 const x=value=>left+(Number(value)-0.05)/0.90*width;
 const y=value=>top+(1-Number(value))*height;
 const series=[['precision','#6fa6ff'],['recall','#ff9b71'],['f1','#63d7b2']];
 return <div className="threshold-chart-wrap"><svg viewBox="0 0 770 225" role="img" aria-label="Validation precision recall and F1 by probability threshold"><g className="curve-grid">{[0,0.5,1].map(t=><React.Fragment key={t}><line x1={left} y1={y(t)} x2={left+width} y2={y(t)}/><text x="8" y={y(t)+4}>{t.toFixed(1)}</text></React.Fragment>)}</g><line x1={x(selected)} y1={top} x2={x(selected)} y2={top+height} className="threshold-marker"/>{series.map(([key,color])=><polyline key={key} fill="none" stroke={color} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" points={(rows||[]).map(row=>`${x(row.threshold)},${y(row[key])}`).join(' ')}/>)}<line x1={left} y1={top+height} x2={left+width} y2={top+height} className="curve-axis"/>{[0.05,0.25,0.5,0.75,0.95].map(t=><text key={t} x={x(t)} y="211" textAnchor="middle">{t.toFixed(2)}</text>)}</svg><div className="threshold-legend">{series.map(([key,color])=><span key={key}><i style={{background:color}}/>{key.toUpperCase()}</span>)}</div></div>;
}
