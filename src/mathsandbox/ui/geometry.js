/* Local Plotly views. Source IR and exact/numeric metadata stay on the server. */
window.renderGeometry = async function (plot, view) {
  const ids = ['plot', 'plot-secondary', 'plot-tertiary'];
  const $ = id => document.getElementById(id);
  const base = {margin:{t:35,r:25,b:55,l:65},paper_bgcolor:'white',plot_bgcolor:'white',showlegend:false};
  const config = {responsive:true,displaylogo:false};
  function colorChart(id) {
    return Plotly.newPlot(id,[{type:'image',z:plot.rgba,x0:plot.x[0],dx:plot.x[1]-plot.x[0],y0:plot.y[0],dy:plot.y[1]-plot.y[0],
      zsmooth:false,customdata:plot.hover,hovertemplate:'z = %{customdata[0]}<br>f(z) ≈ %{customdata[1]}<br>|f(z)| ≈ %{customdata[2]}<extra></extra>'}],
      {...base,title:{text:'Domain coloring'},xaxis:{title:{text:'Re z'},range:[plot.x[0],plot.x.at(-1)]},
        yaxis:{title:{text:'Im z'},range:[plot.y[0],plot.y.at(-1)],scaleanchor:'x'}},config);
  }
  function magnitudeChart(id) {
    return Plotly.newPlot(id,[{type:'surface',x:plot.x,y:plot.y,z:plot.height,surfacecolor:plot.phase.map(row=>row.map(v=>v??0)),
      cmin:-Math.PI,cmax:Math.PI,colorscale:plot.phase_colorscale,connectgaps:false,customdata:plot.hover,
      colorbar:{title:{text:'arg f(z)'},tickvals:[-Math.PI,0,Math.PI],ticktext:['−π','0','π']},
      hovertemplate:'z = %{customdata[0]}<br>f(z) ≈ %{customdata[1]}<br>|f(z)| ≈ %{customdata[2]}<extra></extra>'}],
      {...base,title:{text:'Complex magnitude · phase color'},scene:{xaxis:{title:{text:'Re z'}},yaxis:{title:{text:'Im z'}},
        zaxis:{title:{text:view.height_scale==='log1p'?'ln(1+|f(z)|)':'|f(z)|'}}}},config);
  }
  function sphereChart(id) {
    const x=[],y=[],z=[];
    for(let lat=-3;lat<=3;lat++) {const theta=lat*Math.PI/8;for(let j=0;j<=48;j++) {const phi=j*Math.PI/24;x.push(Math.cos(theta)*Math.cos(phi));y.push(Math.cos(theta)*Math.sin(phi));z.push(Math.sin(theta));}x.push(null);y.push(null);z.push(null);}
    for(let meridian=0;meridian<8;meridian++){const phi=meridian*Math.PI/4;for(let j=0;j<=32;j++){const theta=-Math.PI/2+j*Math.PI/32;x.push(Math.cos(theta)*Math.cos(phi));y.push(Math.cos(theta)*Math.sin(phi));z.push(Math.sin(theta));}x.push(null);y.push(null);z.push(null);}
    const points=plot.sphere;
    return Plotly.newPlot(id,[{type:'scatter3d',x,y,z,mode:'lines',line:{color:'#c8d4ce',width:1},hoverinfo:'skip'},
      {type:'scatter3d',x:points.map(p=>p.xyz[0]),y:points.map(p=>p.xyz[1]),z:points.map(p=>p.xyz[2]),mode:'markers',
       marker:{size:2,color:points.map(p=>p.phase??0),cmin:-Math.PI,cmax:Math.PI,colorscale:plot.phase_colorscale},customdata:points.map(p=>[p.input,p.value]),
       hovertemplate:'z = %{customdata[0]}<br>f(z) ≈ %{customdata[1]}<extra></extra>'},
      {type:'scatter3d',x:[0,0],y:[0,0],z:[1,-1],mode:'markers+text',text:['∞ reference','0 reference'],textposition:'top center',marker:{size:4,color:'#173c3b'},hoverinfo:'text'}],
      {...base,title:{text:'Riemann sphere · sampled f(z)'},scene:{aspectmode:'cube',xaxis:{title:{text:'X'},range:[-1.2,1.2]},yaxis:{title:{text:'Y'},range:[-1.2,1.2]},zaxis:{title:{text:'Z'},range:[-1.2,1.2]}}},config);
  }
  function valuationChart() {
    const pairs=[['input',plot.input_valuation,plot.input],['f(input)',plot.valuation,plot.rational]];
    const finite=pairs.filter(p=>p[1]!=='infinity');
    const zero=pairs.filter(p=>p[1]==='infinity').map(p=>`${p[0]} = 0: valuation ∞, norm 0`).join('; ');
    return Plotly.newPlot('plot',[{type:'bar',x:finite.map(p=>p[0]),y:finite.map(p=>p[1]),text:finite.map(p=>String(p[1])),textposition:'auto',
      customdata:finite.map(p=>p[2]),marker:{color:'#28776b'},hovertemplate:'%{x} = %{customdata}<br>v_p = %{y}<extra></extra>'}],
      {...base,title:{text:`Exact ${plot.prime}-adic valuations`},yaxis:{title:{text:`v_${plot.prime}`}},annotations:zero?[{text:zero,x:0.5,y:1.12,xref:'paper',yref:'paper',showarrow:false}]:[]},config);
  }
  function treeChart() {
    const nodes=plot.nodes, byId=new Map(nodes.map(n=>[n.id,n]));
    const branches=[{x:[],y:[]},{x:[],y:[]}];
    for(const node of nodes){if(node.parent===null)continue;const parent=byId.get(node.parent),line=branches[node.selected?1:0];line.x.push(parent.x,node.x,null);line.y.push(-parent.depth,-node.depth,null);}
    const traces=branches.map((line,index)=>({type:'scatter',...line,mode:'lines',line:{color:index?'#28776b':'#d4dfd8',width:index?3:1},hoverinfo:'skip'}));
    traces.push({type:'scatter',x:nodes.map(n=>n.x),y:nodes.map(n=>-n.depth),mode:'markers',marker:{size:nodes.map(n=>n.selected?9:5),color:nodes.map(n=>n.selected?'#28776b':'#d4dfd8')},
      customdata:nodes.map(n=>[String(n.residue),String(n.modulus),n.selected?'Selected residue':'Sibling; subtree not expanded']),
      hovertemplate:'%{customdata[0]} mod %{customdata[1]}<br>%{customdata[2]}<extra></extra>'});
    return Plotly.newPlot('plot',traces,{...base,title:{text:`${plot.prime}-adic ${plot.unit_part===null?"zero":"unit"} residues · ${plot.precision} digits`},xaxis:{visible:false},
      yaxis:{title:{text:'Nested residue balls'},tickvals:Array.from({length:plot.precision+1},(_,i)=>-i),ticktext:Array.from({length:plot.precision+1},(_,i)=>`mod ${plot.prime}^${i}`),range:[-plot.precision-0.4,0.4]}},config);
  }
  if(plot.kind==='complex'){
    $('geometry-summary').textContent='Hue = arg f(z); brightness = |f(z)|/(1+|f(z)|). Zero is black and has no phase. Transparent gaps mask excluded samples and principal cuts. Sphere markers are finite samples; the north marker is the reference infinity point.';
    if(view.geometry==='complex-compare'){$('plot-secondary').hidden=false;$('plot-tertiary').hidden=false;await Promise.all([colorChart(ids[0]),magnitudeChart(ids[1]),sphereChart(ids[2])]);}
    else if(view.geometry==='complex-magnitude')await magnitudeChart(ids[0]);
    else if(view.geometry==='riemann-sphere')await sphereChart(ids[0]);
    else await colorChart(ids[0]);
  }else{
    $('geometry-summary').textContent=`q = ${plot.rational}; v_${plot.prime}(q) = ${plot.valuation==='infinity'?'∞':plot.valuation}; |q|_${plot.prime} = ${plot.norm}. ${plot.unit_part===null?'Zero residue path.':`q = p^${plot.valuation} × unit; unit = ${plot.unit_part}; unit digits (least significant first): ${plot.digits.join(', ')}.`} Tree layout shows ultrametric containment, not Euclidean distance; only the selected path and siblings are expanded.`;
    if(view.geometry==='padic-tree')await treeChart();else await valuationChart();
  }
};
