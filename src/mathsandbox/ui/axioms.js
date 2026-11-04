/* Only textContent renders user formulas and solver artifacts. */
(()=>{
 const $=id=>document.getElementById('axiom-'+id);let ctx,data,draft=false;
 window.axiomState=value=>{if(!value)return;if(draft&&value.active?.id===data?.active?.id)return;data=value;draft=false;
  $('universe').replaceChildren(new Option('Select a universe',''));
  for(const u of value.universes)$('universe').add(new Option(`${u.name} · rev ${u.revision}`,u.id));
  $('universe').value=value.active?.id??'';$('editor').hidden=!value.active;
  if(!value.active)return;
  const u=value.active,s=value.settings;
  for(const [id,value] of Object.entries({name:u.name,signature:u.signature_text,source:u.source_text,logic:u.logic,policy:u.branch_policy,pinned:s.pinned,conjecture:s.conjecture}))$(id).value=value;
  $('history').replaceChildren();$('result').textContent='';$('model').textContent='';$('repairs').replaceChildren();
  for(const entry of [...value.records].reverse()){
   const b=document.createElement('button');b.textContent=`${entry.record.operation}: ${entry.record.status} · ${entry.current?'source matches':'STALE'} `;
   b.onclick=()=>show(entry);$('history').append(b);
  }
  if(value.records.length)show(value.records.at(-1));
 };
 function showModel(model){
  $('model').textContent='';if(!model)return;
  const lines=['Finite model (independently checked):'];
  for(const s of model.signature){
   if(s.kind==='constant'){lines.push(`${s.name} = ${model.elements[model.constants[s.id]]}`);continue;}
   const table=model.tables[s.id];lines.push(`${s.name}:`);
   for(let i=0;i<table.length;i++){
    let n=i;const args=[];for(let j=0;j<s.arity;j++){args.unshift(model.elements[n%model.size]);n=Math.floor(n/model.size);}
    lines.push(`  (${args.join(', ')}) → ${s.kind==='relation'?table[i]:model.elements[table[i]]}`);
   }
  }
  $('model').textContent=lines.join('\n');
 }
 function show(entry){
  const r=entry.record;showModel(r.details.finite_model?.model??r.details.countermodel?.model);$('result').textContent=JSON.stringify({status:r.status,source_revision:r.universe_revision,current:entry.current,backend:r.backend,backend_version:r.backend_version,evidence:r.details},null,2);
  $('repairs').replaceChildren();
  if(entry.current)for(const [index,candidate] of (r.details.candidates??[]).entries()){
   const b=document.createElement('button');b.textContent=`Fork repair: remove ${candidate.remove.join(', ')}`;
   b.onclick=()=>ctx.task(async()=>{await window.axiomSave();window.axiomState(await ctx.api('/api/axioms/apply-repair',{record_id:r.id,candidate:index}));ctx.markDirty();});$('repairs').append(b);
  }
 }
 window.axiomDiscardDraft=()=>{draft=false;};
 window.axiomSave=async()=>{
  if(!data?.active||!draft)return;
  const body={};for(const [key,id] of Object.entries({name:'name',source_text:'source',signature_text:'signature',logic:'logic',branch_policy:'policy',pinned:'pinned',conjecture:'conjecture'}))body[key]=$(id).value;
  const saved=await ctx.api('/api/axioms/edit',body);draft=false;window.axiomState(saved);
 };
 window.axiomBind=value=>{ctx=value;
  for(const template of ['star-contradiction','projection','semigroup','monoid','group','ring','field','principal-root','multivalued-root'])$('template').add(new Option(template,template));
  $('create').onclick=()=>ctx.task(async()=>{await window.axiomSave();window.axiomState(await ctx.api('/api/axioms/create',{template:$('template').value}));ctx.markDirty();});
  $('universe').onchange=()=>{const id=$('universe').value;ctx.task(async()=>{await window.axiomSave();if(id)window.axiomState(await ctx.api('/api/axioms/select',{id}));});};
  for(const el of $('editor').querySelectorAll('input,textarea,select'))el.addEventListener('input',()=>{draft=true;ctx.markDirty();});
  for(const [operation,label] of [['save','Apply editor'],['check','Check foundations'],['finite-model','Finite model (sizes 1–4)'],['projection','Real right projection'],['repair','Find repairs'],['query','Test conjecture'],['fork','Fork universe']]){
   const b=document.createElement('button');b.textContent=label;b.id='axiom-'+operation;b.onclick=()=>ctx.task(async()=>{await window.axiomSave();if(operation==='fork')window.axiomState(await ctx.api('/api/axioms/fork',{}));else if(operation!=='save'){const result=await ctx.api('/api/axioms/run',{operation});window.axiomState(result.state);}ctx.markDirty();});$('actions').append(b);
  }
 };
})();
