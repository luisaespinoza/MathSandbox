"""Bounded A4 computations with typed results and historical provenance."""
from dataclasses import asdict, replace
from copy import deepcopy
import json
import multiprocessing as multiprocessing
import sympy as sp
import mpmath as mp
from ..core.ir import Provenance, identity
from .compiler import Compiler, center
from .records import AnalysisRecord
from .series import make_germ, germ_details, cauchy
from .continuation import transport
from .registry import BUILTINS


def provenance(project,obj,method,backend='SymPy',version=None):
    return Provenance(obj.id,obj.revision,tuple(sorted((key,project.objects[key].revision) for key in project.closure(obj.id))),
                      method,backend,version or sp.__version__,obj.context,('A4:explicit-source-domain-and-branch-retention',))


def parameter_constraint(compiler,dependent,parameters):
    names=[parameter.value.split(':')[0] for parameter in compiler.obj.parameters]
    if dependent not in names or len(parameters)!=2 or len(set(parameters))!=2 or dependent in parameters or any(p not in names for p in parameters):
        raise ValueError("Choose one dependent variable and two distinct parameter names from the source signature")
    symbols=dict(zip(names,compiler.parameters))
    expression=compiler.expression
    if not expression.is_polynomial(*compiler.parameters) or compiler.exclusions:
        raise ValueError("Implicit constraints currently require a polynomial F with no source denominators")
    y=symbols[dependent]
    a,b=[symbols[name] for name in parameters]
    fy,fa,fb=sp.diff(expression,y),sp.diff(expression,a),sp.diff(expression,b)
    if fy==0:
        raise ValueError("F_y is identically zero; no regular implicit branch is licensed")
    gcd=sp.gcd(fa,fb)
    ca,cb=(sp.Integer(1),sp.Integer(0)) if gcd==0 else (sp.cancel(fb/gcd),sp.cancel(-fa/gcd))
    residual=sp.simplify(ca*fa+cb*fb)
    if residual!=0:
        raise ValueError("Unable to check parameter elimination identity")
    partials=[]
    for name in parameters:
        key='partial:'+identity()
        label=dependent+'_'+name
        variable=sp.Dummy(label if label not in names else 'D['+dependent+','+name+']')
        compiler.symbols[key]=variable
        partials.append((key,variable))
    relation=sp.expand(ca*partials[0][1]+cb*partials[1][1])
    conditions=tuple(compiler.display(factor)+' != 0' for factor,power in sp.factor_list(fy)[1])
    return compiler.reconstruct(relation),conditions,{
        'constraint':compiler.display(relation)+' = 0','dependent':dependent,'parameters':parameters,
        'F_y':compiler.display(fy),'parameter_partials':{parameters[0]:compiler.display(-fa/fy),parameters[1]:compiler.display(-fb/fy)},
        'syzygy_coefficients':[compiler.display(ca),compiler.display(cb)],'checked_syzygy_residual':str(residual),
        'derivative_bindings':{key:variable.name for key,variable in partials},
        'source_equation':compiler.obj.original_definition.split('=',1)[1].strip()+' = 0',
        'scope':'Necessary identity only on F=0 and F_y != 0; not a complete PDE replacement'}


def execute(project,name,method,options):
    obj=project.objects[project.names[name]]
    prov=provenance(project,obj,method)
    compiler=Compiler(project,name)
    assumptions=[]
    exclusions=list(compiler.source_exclusions())
    germ=None
    result=None
    details={}
    status='exact-symbolic'
    reconstruction='Original definition and source exclusions retained; no source replacement'
    digits=options.get('digits',30)
    if type(digits) is not int or not 15<=digits<=100:
        raise ValueError("Working precision must be 15..100 decimal digits")
    with mp.workdps(digits):
        if method in ('taylor','laurent','continue','cauchy'):
            c=center(options.get('center_real','0'),options.get('center_imag','0'))
            order=options.get('order',32)
            germ=make_germ(compiler,prov,'laurent' if method=='laurent' else 'taylor',c,order,
                           options.get('coefficient_method','series') if method not in ('continue','cauchy') else 'recurrence' if method=='continue' else 'series')
            details=germ_details(compiler,germ,digits)
            assumptions=['One-valued analytic/meromorphic supported template on the recorded disk or punctured annulus']
            reconstruction='Retain germ center, coefficients, source exclusions, and the explicit truncation model'
            if method=='cauchy':
                details['cauchy']=cauchy(compiler,c,order,options.get('radius','1/2'),digits,{value.power:compiler.convert(value.value) for value in germ.coefficients})
                status='numerically-computed'
                prov=provenance(project,obj,method,'SymPy + mpmath',sp.__version__+' / '+mp.__version__)
            if method=='continue':
                details['continuation']=transport(compiler,c,order,digits,options.get('path','0,0;2,0'))
                status='numerically-computed'
                prov=provenance(project,obj,method,'SymPy + mpmath',sp.__version__+' / '+mp.__version__)
        elif method=='parameter-constraint':
            result,conditions,details=parameter_constraint(compiler,options.get('dependent','y'),options.get('parameters',['a','b']))
            assumptions=['Original implicit equation F=0',*conditions]
            exclusions.append(compiler.display(sp.diff(compiler.expression,compiler.parameters[[p.value.split(':')[0] for p in obj.parameters].index(options.get('dependent','y'))]))+' = 0')
            status='conditional-symbolic-identity'
            reconstruction='Retain original F=0, regular branch selection, and reconstruction/initial data; constraint alone is necessary, not complete'
        else:
            if method not in project.transform_registry.definitions:
                raise ValueError("Unknown transformation identity")
            definition=project.transform_registry.definitions[method]
            known=next((d for d in BUILTINS if d.id==method),None)
            if known is not None and definition!=known:
                raise ValueError("Builtin transformation semantics were changed")
            expression=compiler.expression
            if definition.operation=='differentiate':
                if len(compiler.parameters)!=1:
                    raise ValueError("Select a unary function for ordinary differentiation")
                value=sp.diff(expression,compiler.parameters[0])
                reconstruction='Recovering the original from its derivative requires an integration constant and original domain'
            elif definition.operation in ('factor','simplify'):
                value=getattr(sp,definition.operation)(expression)
                residual=sp.simplify(value-expression)
                details['identity_residual']=str(residual)
                if residual!=0:
                    status='exploratory'
                    details['verification']='Output identity check did not reduce to zero; equivalence is unproved'
            elif definition.operation=='rewrite':
                if len(compiler.parameters)!=1:
                    raise ValueError("Custom rewrite templates currently have one parameter")
                bindings={definition.parameter.value:compiler.parameters[0]}
                pattern=compiler.convert(definition.pattern,bindings)
                replacement=compiler.convert(definition.replacement,bindings)
                value=expression.subs(pattern,replacement,simultaneous=True)
                checked=sp.simplify(pattern-replacement)==0 and sp.simplify(value-expression)==0
                status='exact-symbolic' if checked else 'exploratory'
                details.update(pattern=compiler.display(pattern),replacement=compiler.display(replacement),
                               verification='Symbolic equivalence checked under recorded context' if checked else 'Unproved rewrite; output is not certified equivalent')
                exclusions=list(compiler.source_exclusions())
            else:
                raise ValueError("No evaluator for this declarative transformation")
            result=compiler.reconstruct(value)
            compiler.convert(result)  # Retain any new output restrictions as well as source restrictions.
            details['expression']=compiler.display(value)
        assumptions.extend(compiler.display(value)+" != 0" for value in compiler.exclusions)
        exclusions.extend(compiler.source_exclusions())
        details["source_definition"]=obj.original_definition
        record=AnalysisRecord(identity(),method,status,result,tuple(dict.fromkeys(assumptions)),tuple(dict.fromkeys(exclusions)),reconstruction,details,prov)
        return {'germ':germ,'record':record}


def _worker(writer,project,name,method,options):
    try:
        writer.send(execute(project,name,method,options))
    except Exception as error:
        writer.send({'error':str(error) or type(error).__name__})
    finally:
        writer.close()


def run(project,name,method,*,timeout=25,**options):
    if name not in project.names:
        raise ValueError("Select a defined source function")
    runtime=multiprocessing.get_context('spawn')
    reader,writer=runtime.Pipe(duplex=False)
    process=runtime.Process(target=_worker,args=(writer,project,name,method,options))
    process.start()
    writer.close()
    try:
        if not reader.poll(timeout):
            raise ValueError("Analysis timed out; reduce the order or simplify the source")
        try:
            value=reader.recv()
        except EOFError:
            raise ValueError("Analysis worker exited without a result") from None
        if 'error' in value:
            raise ValueError(value['error'])
    finally:
        reader.close()
        if process.is_alive():
            process.terminate()
        process.join()
    record=replace(value['record'],details=json.loads(json.dumps(value['record'].details,allow_nan=False)))
    if value['germ'] is not None:
        project.analytic_germs[value['germ'].id]=value['germ']
    project.analysis_records.append(deepcopy(record))
    return record


def current(project,provenance):
    return (provenance.source_id in project.objects and project.objects[provenance.source_id].revision==provenance.source_revision
            and provenance.source_id in dict(provenance.dependency_revisions) and all(key in project.objects and project.objects[key].revision==revision for key,revision in provenance.dependency_revisions))


def continue_germ(project, germ_id, path, *, digits=30, timeout=25):
    germ=project.analytic_germs[germ_id]
    if germ.kind!='taylor' or not current(project,germ.provenance):
        raise ValueError("Germ is stale or is not a Taylor germ; recompute from current definitions")
    obj=project.objects[germ.provenance.source_id]
    compiler=Compiler(project,obj.name)
    c=compiler.convert(germ.center)
    if c.free_symbols:
        raise ValueError("Germ center must be a constant")
    # Coefficients loaded from JSON are never trusted as a numerical seed.
    return run(project,obj.name,'continue',timeout=timeout,center_real=str(sp.re(c)),center_imag=str(sp.im(c)),
               order=max(value.power for value in germ.coefficients)+1,digits=digits,path=path)
