"""Semantic checks for the bounded axiom laboratory."""
from copy import deepcopy
from dataclasses import replace
import json
import pytest
pytest.importorskip('z3')
from mathsandbox.core.project import Project
from mathsandbox.axioms import backend,engine,models
from mathsandbox.axioms.universes import create,edit,update,signature_text
from mathsandbox.axioms.parser import Parser
from mathsandbox.storage.json_project import dumps,loads
from mathsandbox.ui.workbench import Workbench

@pytest.fixture
def star():return create()

def test_contradiction_and_blocked_explosion(star):
    status,details=engine.execute(star,'check',{})
    assert status=='witnessed-contradiction'
    check=details['unrestricted_check']
    assert check['outcome']=='unsat' and check['unsat_core']
    assert engine.execute(star,'query',{'conjecture':'a=a'})[0]=='blocked-inconsistent'


def test_projection_and_properties():
    u=create('projection');result=backend.real_projection(u)
    assert result['valid']
    p=engine.projection_properties(u)
    for key in ('associative','left_distributive','left_unit_one'):assert p[key]['holds']
    for key in ('right_distributive','commutative','right_unit_one'):assert not p[key]['holds']
    status,details=engine.execute(u,'query',{'conjecture':'star(a,b)=star(b,a)'})
    assert status=='countermodel-constructed'
    assert details['countermodel']['model']


def test_field_independent_model():
    u=create('field');result=backend.finite(u)
    model=result['model'];assert model and models.verify(u,model)['valid']
    corrupt=deepcopy(model);key=next(iter(corrupt['tables']));corrupt['tables'][key]=[]
    with pytest.raises(ValueError,match='total'):models.verify(u,corrupt)


def test_no_small_model_is_undetermined():
    u=create('group');sig='c0/0, c1/0, c2/0, c3/0, c4/0'
    text='\n'.join(f'd{i}{j}: c{i}!=c{j}' for i in range(5) for j in range(i+1,5))
    u=update(u,text,sig)
    assert engine.execute(u,'check',{})[0]=='undetermined'


def test_repair_and_fresh_fork(star):
    w=Workbench();w.axiom_create({'template':'star-contradiction'})
    u=w.project.universes[w.logic_settings['active']]
    pins=w.logic_settings['pinned'].split(',')
    status,details=engine.execute(u,'repair',{'pinned':pins})
    assert status=='repair-candidates'
    assert [c['remove'] for c in details['candidates']]==[['star_right_dist']]
    record=engine.run(w.project,u.id,'repair',pinned=pins)
    fork=engine.apply_repair(w.project,record.id,0,pins)
    assert fork.parent_id==u.id and fork.id!=u.id
    assert w.project.universes[u.id]==u
    assert 'star_right_dist' not in {a.label for a in fork.axioms}
    with pytest.raises(ValueError,match='Pinned'):engine.apply_repair(w.project,record.id,0,['star_right_dist'])
    w.project.universes[u.id]=edit(u,u.source_text+'\nextra: a=a')
    assert not engine.current(w.project,record)
    with pytest.raises(ValueError,match='stale'):engine.apply_repair(w.project,record.id,0)

@pytest.mark.parametrize('template',['principal-root','multivalued-root'])
def test_root_semantics_not_erased(template):
    u=create(template)
    assert engine.execute(u,'check',{})[0]=='backend-incompatible'


def test_nonclassical_not_translated(star):
    assert engine.execute(replace(star,logic='paraconsistent'),'query',{'conjecture':'a=a'})[0]=='backend-incompatible'

@pytest.mark.parametrize('text',['__import__("os")','star(a)','a.__class__=a','a[0]=a','lambda a: a','star(a,b,c)=a'])
def test_parser_rejects_unsafe_or_malformed(star,text):
    with pytest.raises(ValueError):Parser(star.signature).formula(text)


def test_edit_is_typed_and_revisions_preserved(star):
    same=update(star,star.source_text,signature_text(star));assert same==star
    changed=edit(star,star.source_text.replace('star_10: star(1,0)=0','star_10: star(1,0)=1'))
    before={a.label:a for a in star.axioms};after={a.label:a for a in changed.axioms}
    assert changed.revision==2
    assert after['star_10'].id==before['star_10'].id
    assert after['star_10'].revision==2 and after['distinct']==before['distinct']


def test_roundtrip_and_tamper(star):
    p=Project();p.universes[star.id]=star
    engine.run(p,star.id,'check')
    loaded=loads(dumps(p));assert loaded.universes==p.universes
    assert loaded.logic_records==p.logic_records
    data=json.loads(dumps(p));data['universes'][0]['axioms'][0]['text']='a=a'
    with pytest.raises(ValueError,match='disagrees'):loads(json.dumps(data))
    data=json.loads(dumps(p));data['universes'][0]['id']='standard-real'
    with pytest.raises(ValueError):loads(json.dumps(data))


def test_missing_optional_backend(monkeypatch,star):
    def missing():raise ValueError('Install mathsandbox[axioms]')
    monkeypatch.setattr(engine,'require',missing)
    status,details=engine.execute(star,'check',{})
    assert status=='backend-incompatible' and details['capability']=='optional-backend-unavailable'


def test_workbench_save_restore_and_atomic_edit():
    w=Workbench();w.axiom_create({'template':'projection'})
    state=w.axiom_state();u=state['active']
    with pytest.raises(ValueError):w.axiom_edit({'source_text':'bad: missing(a)=a','signature_text':u['signature_text']})
    assert w.axiom_state()==state
    other=Workbench();other.restore(w.export())
    assert other.axiom_state()==state


def test_imported_repair_evidence_is_rechecked(star):
    p=Project();p.universes[star.id]=star
    record=engine.run(p,star.id,'repair',pinned=['star_10','star_01','distinct'])
    forged=replace(record,details={'pinned':[],'candidates':[{'remove':['star_assoc'],'witness':{'valid':True}}]})
    p.logic_records=[forged];loaded=loads(dumps(p))
    with pytest.raises(ValueError,match='freshly validated'):
        engine.apply_repair(loaded,forged.id,0)
    assert len(loaded.universes)==1


def test_entailment_is_not_a_certificate():
    status,details=engine.execute(create('projection'),'query',{'conjecture':'a=a'})
    assert status=='backend-entailment' and details['certified'] is False


def test_empty_axioms_and_nullary_relation():
    u=update(create('group'),'','p?/0, c/0')
    assert backend.finite(u)['model']


def test_formula_syntax_errors_are_user_errors(star):
    with pytest.raises(ValueError):Parser(star.signature).formula('a=')
