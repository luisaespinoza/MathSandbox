/* Analysis previews are separate from source definitions and never mutate them. */
window.analysisState = function(data){
 const $=id=>document.getElementById(id), selected=data.analysis_settings??{};
 const builtins=[['taylor','Taylor coefficients'],['laurent','Laurent coefficients'],['cauchy','Cauchy coefficient quadrature'],['continue','Taylor continuation'],['parameter-constraint','Implicit parameter constraint']];
 $('analysis-method').replaceChildren();for(const [value,label] of builtins)$('analysis-method').add(new Option(label,value));
 for(const rule of data.transformations??[])$('analysis-method').add(new Option(rule.description,rule.id));
 for(const key of ['method','center_real','center_imag','order','coefficient_method','radius','path','dependent','parameters'])if(selected[key]!==undefined)$('analysis-'+key.replaceAll('_','-')).value=selected[key];
 $('analysis-history').replaceChildren();
 for(const entry of [...(data.analysis_records??[])].reverse()){
  const item=document.createElement('li'),button=document.createElement('button');
  button.textContent=`${entry.record.method} · ${entry.record.status} · source rev ${entry.record.provenance.source_revision} · ${entry.current?'revisions match':'STALE source'}`;
  button.onclick=()=>{window.showAnalysis(entry.record,true,!entry.current);};item.append(button);$('analysis-history').append(item);
 }
};
window.analysisOptions=function(){
 const $=id=>document.getElementById(id);return {method:$('analysis-method').value,center_real:$('analysis-center-real').value,center_imag:$('analysis-center-imag').value,order:Number($('analysis-order').value),coefficient_method:$('analysis-coefficient-method').value,radius:$('analysis-radius').value,path:$('analysis-path').value,dependent:$('analysis-dependent').value,parameters:$('analysis-parameters').value};
};
window.clearAnalysis=function(){for(const id of ['coefficient-plot','continuation-plot']){Plotly.purge(id);document.getElementById(id).hidden=true;}document.getElementById('analysis-status').textContent='No current analysis preview';document.getElementById('analysis-result').textContent='';document.getElementById('analysis-provenance').textContent='';};
window.showAnalysis=async function(record,historical=false,stale=false){
 const $=id=>document.getElementById(id),d=record.details;
 window.clearAnalysis();$('analysis-status').textContent=(historical?'Saved historical record · not recomputed · '+(stale?'STALE source · ':''):'')+record.status;
 let text=`Source (rev ${record.provenance.source_revision}): ${d.source_definition??'see source provenance'}\n`+(d.constraint??d.expression??'');
 if(d.continuation){const c=d.continuation;text+=`\n\nContinued value at ${c.endpoint}: ${c.value}\nIndependent reference: ${c.reference_value}\nObserved refinement difference: ${c.error_estimate}\nReference difference: ${c.reference_absolute_difference}\n${c.steps.length} overlapping disks; ${c.working_digits} working digits. No certified error bound.\n${c.method}`;}
 if(d.cauchy)text+='\n\nCauchy estimates (numerical; quadrature error is heuristic):\n'+d.cauchy.coefficients.map(c=>`a[${c.power}] ≈ ${c.coefficient}`).join('\n');
 if(d.coefficients)text+=`${d.kind} germ at ${d.center}; source-domain radius ${d.outer_radius}; ${d.coefficient_method} coefficients\n`+d.coefficients.map(c=>`a[${c.power}] = ${c.coefficient}`).join('\n')+'\n'+d.error_model;
 if(d.verification)text+='\n'+d.verification;
 text+='\n\nAssumptions: '+record.assumptions.join('; ')+'\nExcluded: '+record.exceptional_sets.join('; ')+'\nReconstruction: '+record.reconstruction;
 $('analysis-result').textContent=text;$('analysis-provenance').textContent=JSON.stringify(record.provenance,null,2);
 const config={responsive:true,displaylogo:false};
 if(d.coefficients){$('coefficient-plot').hidden=false;await Plotly.newPlot('coefficient-plot',[{type:'bar',x:d.coefficients.map(c=>c.power),y:d.coefficients.map(c=>c.log_magnitude),customdata:d.coefficients.map(c=>c.coefficient),marker:{color:'#28776b'},hovertemplate:'a[%{x}] = %{customdata}<extra></extra>'}],{margin:{t:35,b:45,l:55,r:15},title:{text:'Exact coefficients · magnitude view'},xaxis:{title:{text:'Integer power'}},yaxis:{title:{text:'log10(1 + |a[n]|)'}}},config);}
 if(d.radius_estimate!==undefined){$('continuation-plot').hidden=false;
  const traces=[],shapes=[];
  if(d.continuation){const steps=d.continuation.steps,points=steps.length?[steps[0].from_coordinates,...steps.map(s=>s.center_coordinates)]:[];traces.push({type:'scatter',x:points.map(p=>p[0]),y:points.map(p=>p[1]),mode:'lines+markers',name:'Transported centers'});for(const step of steps){const p=step.from_coordinates,r=Number(step.radius_estimate);if(Number.isFinite(r))shapes.push({type:'circle',xref:'x',yref:'y',x0:p[0]-r,y0:p[1]-r,x1:p[0]+r,y1:p[1]+r,line:{color:'#cbded7',width:1}});}}
  else{traces.push({x:[0],y:[0],mode:'markers',marker:{symbol:d.kind==='laurent'?'circle-open':'circle'},name:'Local center'});if(d.radius_estimate!==null)shapes.push({type:'circle',x0:-d.radius_estimate,y0:-d.radius_estimate,x1:d.radius_estimate,y1:d.radius_estimate,line:{color:'#28776b'}});}
  await Plotly.newPlot('continuation-plot',traces,{margin:{t:35,b:45,l:55,r:15},title:{text:d.continuation?'Estimated disks along stored path':'Local disk/annulus · coordinates relative to center'},shapes,xaxis:{title:{text:'Re'}},yaxis:{title:{text:'Im'},scaleanchor:'x'},showlegend:false},config);
 }
};
