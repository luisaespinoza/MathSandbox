"""Bounded logic workflows; no historical record licenses a new theorem."""
from copy import deepcopy
from dataclasses import asdict,replace
import itertools
import json
import multiprocessing as multiprocessing
import time
from ..core.ir import identity
from .records import LogicRecord
from .universes import fingerprint,drop,fork
from .parser import Parser
from .backend import compatible,require,unrestricted,finite,real_projection


def foundation(universe):
    check=unrestricted(universe)
    if check['outcome']=='unsat':return 'witnessed-contradiction',{'unrestricted_check':check}
    finite_check=finite(universe)
    if finite_check['model'] is not None:
        return 'model-constructed',{'unrestricted_check':check,'finite_model':finite_check,
                                    'scope':'Explicit independently checked finite model; relative consistency only'}
    projection=real_projection(universe)
    if projection.get('valid'):
        return 'model-constructed',{'unrestricted_check':check,'finite_model':finite_check,'real_projection':projection,
                                    'scope':'Explicit real interpretation validated relative to Z3 real arithmetic'}
    return 'undetermined',{'unrestricted_check':check,'finite_model':finite_check,'projection_attempt':projection,
                           'scope':'No witnessed contradiction or validated model. Bounded failure is not inconsistency or consistency.'}


def projection_properties(universe):
    formulas={'associative':'star(star(a,b),c)=star(a,star(b,c))',
              'left_distributive':'star(a,add(b,c))=add(star(a,b),star(a,c))',
              'right_distributive':'star(add(a,b),c)=add(star(a,c),star(b,c))',
              'commutative':'star(a,b)=star(b,a)','left_unit_one':'star(1,a)=a','right_unit_one':'star(a,1)=a'}
    parser=Parser(universe.signature);checks={}
    for name,text in formulas.items():
        try:
            from .records import Axiom
            trial=replace(universe,axioms=(Axiom('property:'+name,name,text,parser.formula(text)),))
            result=real_projection(trial)
            checks[name]={'holds':result['valid'],'checks':result.get('checks',[])}
        except ValueError:checks[name]={'holds':None,'reason':'Signature does not support this comparison'}
    return checks


def repair_search(universe,pinned,max_deletions=2):
    labels={axiom.label for axiom in universe.axioms}
    if any(label not in labels for label in pinned):raise ValueError('Pinned labels must exist in this universe')
    status,base=foundation(universe)
    if status!='witnessed-contradiction':
        return 'undetermined',{'diagnostic':'Repair search requires a witnessed contradiction first','foundation_status':status,'foundation':base,'candidates':[]}
    removable=[a.label for a in universe.axioms if a.label not in pinned]
    candidates=[];attempts=[];deadline=time.monotonic()+8
    for count in range(1,min(max_deletions,len(removable))+1):
        for removed in itertools.combinations(removable,count):
            if len(attempts)>=32 or time.monotonic()>deadline:break
            candidate=drop(universe,list(removed))
            projection=real_projection(candidate,timeout=80)
            model={'real_projection':projection} if projection.get('valid') else None
            # Prefer a complete ordinary-real interpretation. Fall back to a checked finite model.
            if model is None:
                finite_check=finite(candidate,max_size=3,timeout=100)
                if finite_check['model'] is not None:model={'finite_model':finite_check}
            attempts.append({'removed':list(removed),'model_constructed':model is not None})
            if model is not None:
                candidates.append({'remove':list(removed),'pinned_preserved':list(pinned),'witness':model,
                                   'scope':'Model-backed alternative; not necessarily a field or a globally minimal repair'})
                # Return the smallest witnessed deletion size rather than inventing a preferred theory.
                if len(candidates)>=3:break
        if candidates or len(attempts)>=32 or time.monotonic()>deadline:break
    return ('repair-candidates' if candidates else 'undetermined'),{
        'foundation':base,'candidates':candidates,'attempts':attempts,'pinned':list(pinned),
        'minimality':'Smallest witnessed deletion count within this bounded search; unknown alternatives prevent a global minimality certificate',
        'limits':{'max_deletions':max_deletions,'max_candidates_tested':32,'search_seconds':8}}


def execute(universe,operation,options):
    if not compatible(universe):
        return 'backend-incompatible',{'diagnostic':'Only classical equality with uninterpreted algebraic operations is licensed. Principal complex roots, multivalued roots, and nonclassical logics retain their semantics and are not translated.'}
    try:require()
    except ValueError as error:return 'backend-incompatible', {'diagnostic':str(error),'capability':'optional-backend-unavailable'}
    if operation=='check':return foundation(universe)
    if operation=='finite-model':
        value=finite(universe)
        return ('model-constructed' if value['model'] is not None else 'undetermined'),{'finite_model':value,'scope':'Finite-model search only; finite unsat never proves unrestricted inconsistency'}
    if operation=='projection':
        value=real_projection(universe)
        return ('model-constructed' if value.get('valid') else 'undetermined'),{'real_projection':value,'properties':projection_properties(universe),
                 'scope':'Ordinary additive reals with star(a,b)=b; star is not field multiplication or automatically two-sided unital'}
    if operation=='repair':return repair_search(universe,options.get('pinned',[]))
    if operation=='query':
        goal_text=options.get('conjecture','')
        goal=Parser(universe.signature).formula(goal_text)
        status,base=foundation(universe)
        if status=='witnessed-contradiction':return 'blocked-inconsistent',{'conjecture':goal_text,'foundation':base,'diagnostic':'Ordinary theorem certification is blocked; no entailment by classical explosion is issued'}
        counter=finite(universe,goal)
        if counter['model'] is not None:return 'countermodel-constructed',{'conjecture':goal_text,'countermodel':counter,'foundation':base,
                                                                       'scope':'Checked countermodel to the universal conjecture, satisfying every source axiom'}
        entailment=unrestricted(universe,goal)
        if entailment['outcome']=='unsat':
            return 'backend-entailment' if status=='model-constructed' else 'conditional-entailment',{
                'conjecture':goal_text,'foundation_status':status,'foundation':base,'entailment':entailment,
                'scope':'Conditional on these foundations; Z3 entailment is not an independently checked proof certificate',
                'certified':False}
        return 'undetermined',{'conjecture':goal_text,'foundation_status':status,'foundation':base,'countermodel_search':counter,
                               'entailment_attempt':entailment,'scope':'No proof or checked countermodel found within the configured limits','certified':False}
    raise ValueError('Unknown axiom-laboratory operation')


def _worker(writer,universe,operation,options):
    try:
        status,details=execute(universe,operation,options)
        try:version=require().get_version_string()
        except ValueError:version='not installed'
        writer.send({'status':status,'details':details,'version':version})
    except ValueError as error:writer.send({'error':str(error)})
    except Exception as error:writer.send({'error':'Backend failure: '+str(error)})
    finally:writer.close()


def run(project,universe_id,operation,*,timeout=25,**options):
    universe=project.universes[universe_id]
    runtime=multiprocessing.get_context('spawn');reader,writer=runtime.Pipe(duplex=False)
    process=runtime.Process(target=_worker,args=(writer,universe,operation,options));process.start();writer.close()
    try:
        if not reader.poll(timeout):raise ValueError('Axiom computation timed out; no conclusion is certified')
        try:value=reader.recv()
        except EOFError:raise ValueError('Axiom worker exited without a result') from None
        if 'error' in value:raise ValueError(value['error'])
    finally:
        reader.close()
        if process.is_alive():process.terminate()
        process.join()
    record=LogicRecord('logic:'+identity(),operation,value['status'],universe.id,universe.revision,fingerprint(universe),
                       tuple((a.id,a.revision) for a in universe.axioms),'Z3',value['version'],
                       json.loads(json.dumps(value['details'],allow_nan=False)))
    project.logic_records.append(deepcopy(record));return record


def current(project,record):
    universe=project.universes.get(record.universe_id)
    return universe is not None and universe.revision==record.universe_revision and fingerprint(universe)==record.fingerprint


def apply_repair(project,record_id,index,pinned=()):
    record=next((r for r in project.logic_records if r.id==record_id),None)
    if record is None or record.operation!='repair' or not current(project,record):raise ValueError('Repair record is missing or stale; rerun the search')
    candidates=record.details.get('candidates',[])
    if type(index) is not int or not 0<=index<len(candidates):raise ValueError('Choose an existing repair candidate')
    source=project.universes[record.universe_id];removed=candidates[index]['remove']
    if len(removed)>2:raise ValueError('Repair candidate exceeds the configured deletion bound')
    if any(label not in {a.label for a in source.axioms} for label in pinned):raise ValueError('Pinned labels must exist')
    if any(label in set(record.details.get('pinned',[]))|set(pinned) for label in removed):raise ValueError('Pinned axioms cannot be removed')
    candidate=fork(drop(source,removed),source.name+' — repaired')
    # Imported records never establish a repair: rerun model construction before retaining the fork.
    temporary=type(project)();temporary.universes[candidate.id]=candidate
    verified=run(temporary,candidate.id,'projection')
    if verified.status!='model-constructed':verified=run(temporary,candidate.id,'finite-model')
    if verified.status!='model-constructed':raise ValueError('Candidate has no freshly validated model; repair not applied')
    project.universes[candidate.id]=candidate;project.logic_records.append(deepcopy(verified));return candidate
