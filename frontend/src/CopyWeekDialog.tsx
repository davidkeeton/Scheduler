import {useState} from 'react';

type Issue={target_week:string;index:number;employee:string;reason:string};
type Target={target_week:string;coverage:number;shifts:number;target_has_draft:boolean;issues:Issue[]};
type Summary={source_week:string;source_batch:string;target_week:string;coverage:number;shifts:number;target_has_draft:boolean;issues:Issue[];targets:Target[];count:number;interval:string;every:number;issue_count:number};
export type CopiedWeek={copy_summary:Summary;blocked_shifts:{id:number;reason:string}[];[key:string]:unknown};
type SourceWeek={week:string;batch:string};
type Props={currentWeek:string;currentHasSchedule:boolean;sourceWeeks:SourceWeek[];onClose:()=>void;onCopied:(result:CopiedWeek)=>void};
function offsetWeek(value:string,count:number){const date=new Date(value+'T12:00:00Z');date.setUTCDate(date.getUTCDate()+7*count);return date.toISOString().slice(0,10)}
export default function CopyWeekDialog({currentWeek,currentHasSchedule,sourceWeeks,onClose,onCopied}:Props){
 const initialSource=currentHasSchedule?currentWeek:(sourceWeeks.find(x=>x.week<currentWeek)?.week||offsetWeek(currentWeek,-1));
 const [sourceWeek,setSourceWeek]=useState(initialSource);
 const [customSource,setCustomSource]=useState(!sourceWeeks.some(x=>x.week===initialSource));
 const [targetMode,setTargetMode]=useState<'after'|'specific'>(currentHasSchedule?'after':'specific');
 const [offset,setOffset]=useState(1);const [specificTarget,setSpecificTarget]=useState(currentWeek);
 const [interval,setInterval]=useState('week');const [every,setEvery]=useState(1);const [count,setCount]=useState(1);
 const [preview,setPreview]=useState<Summary|null>(null);const [replace,setReplace]=useState(false);
 const [busy,setBusy]=useState(false);const [error,setError]=useState('');
 const firstTarget=targetMode==='after'?offsetWeek(sourceWeek,offset):specificTarget;
 const clear=()=>{setPreview(null);setReplace(false)};
 async function request(apply:boolean){
  setBusy(true);setError('');
  try{
   const response=await fetch('/api/copy-week',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_week:sourceWeek,target_week:firstTarget,interval,every,count,preview:!apply,replace})});
   const result=await response.json();
   if(!response.ok)throw Error(result.error||'Could not copy schedule');
   if(apply)onCopied(result as CopiedWeek);else setPreview(result as Summary);
  }catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose()}}><section className="modal copy-modal" role="dialog" aria-modal="true" aria-label="Copy schedule weeks">
  <div className="modal-head"><h2>Copy schedule</h2><button onClick={onClose} aria-label="Close">×</button></div>
  <p className="form-hint">Copy Coverage and assignments for all teams. A week with a schedule defaults to the next week; an empty week defaults to copying a previous schedule into the displayed week.</p>
  <div className="form-grid">
   <label>Copy from week<select value={customSource?'custom':sourceWeek} onChange={e=>{if(e.target.value==='custom'){setCustomSource(true)}else{setCustomSource(false);setSourceWeek(e.target.value)}clear()}}>{sourceWeeks.map(x=><option key={x.week} value={x.week}>{x.week} · {x.batch}</option>)}<option value="custom">Enter another week…</option></select></label>
   {customSource&&<label>Source date<input type="date" value={sourceWeek} onChange={e=>{setSourceWeek(e.target.value);clear()}}/></label>}
   <label>First target<select value={targetMode} onChange={e=>{setTargetMode(e.target.value as 'after'|'specific');clear()}}><option value="after">Weeks after source</option><option value="specific">Choose a week</option></select></label>
   {targetMode==='after'?<label>Weeks after source<input type="number" min="1" max="104" value={offset} onChange={e=>{setOffset(Number(e.target.value));clear()}}/></label>:<label>Target week<input type="date" value={specificTarget} onChange={e=>{setSpecificTarget(e.target.value);clear()}}/></label>}
  </div><p className="copy-destination">First target: <strong>{firstTarget}</strong></p>
  <h3>Repeat into more weeks</h3><div className="form-grid">
   <label>Repeat every<input type="number" min="1" max="12" value={every} onChange={e=>{setEvery(Number(e.target.value));clear()}}/></label>
   <label>Interval<select value={interval} onChange={e=>{setInterval(e.target.value);clear()}}><option value="week">Week</option><option value="month">Month</option><option value="year">Year</option></select></label>
   <label>Number of copies<input type="number" min="1" max={interval==='week'?52:interval==='month'?24:5} value={count} onChange={e=>{setCount(Number(e.target.value));clear()}}/></label>
  </div>
  <button className="secondary" disabled={busy||!sourceWeek||!firstTarget||offset<1||every<1||count<1} onClick={()=>request(false)}>Preview target weeks</button>
  {error&&<p className="copy-error" role="alert">{error}</p>}
  {preview&&<div className="copy-preview"><strong>{preview.count} target week(s) · {preview.coverage} Coverage periods · {preview.shifts} shifts</strong><p>Source: {preview.source_week} {preview.source_batch}</p><div className="copy-targets">{preview.targets.map(t=><div key={t.target_week}><strong>{t.target_week}</strong> · {t.coverage} Coverage · {t.shifts} shifts{t.target_has_draft?' · existing draft':''}{t.issues.length?` · ${t.issues.length} issue(s)`:''}</div>)}</div>{preview.target_has_draft&&<label className="copy-replace"><input type="checkbox" checked={replace} onChange={e=>setReplace(e.target.checked)}/> Replace existing drafts in the listed target weeks</label>}{preview.issue_count?<div className="copy-issues"><strong>{preview.issue_count} assignment issue(s) to review</strong>{preview.issues.map((x,i)=><div key={i}>{x.target_week} · {x.employee}: {x.reason}</div>)}</div>:<p>No assignment conflicts found in the preview.</p>}</div>}
  <div className="modal-actions"><button className="quiet" onClick={onClose}>Cancel</button><button className="primary" disabled={busy||!preview||(preview.target_has_draft&&!replace)} onClick={()=>request(true)}>Create {preview?.count||0} draft week(s)</button></div>
 </section></div>;
}
