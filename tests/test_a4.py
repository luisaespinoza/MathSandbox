from dataclasses import asdict, replace
import json
import mpmath as mp
import pytest
import sympy as sp
from mathsandbox import Context, OperatorDefinition, Project
from mathsandbox.adapters.complex_numeric import COMPLEX_CONTEXT
from mathsandbox.analysis.compiler import Compiler
from mathsandbox.analysis.engine import run, current, continue_germ
from mathsandbox.analysis.registry import TransformationDefinition
from mathsandbox.analysis.continuation import transport
from mathsandbox.storage.json_project import dumps, loads
from mathsandbox.ui.workbench import Workbench


def project(text,context=COMPLEX_CONTEXT):
    p=Project();p.define(text,context);return p


def coefficients(record):
    return {row['power']:row['coefficient'] for row in record.details['coefficients']}


@pytest.mark.parametrize('method',['series','derivative','recurrence'])
def test_taylor_exact_coefficients_radius_and_source_preservation(method):
    p=project('f(z)=1/(1+z^2)')
    original=p.objects.copy()
    result=run(p,'f','taylor',order=10,coefficient_method=method)
    assert coefficients(result)=={i:str((-1)**(i//2) if i%2==0 else 0) for i in range(10)}
    assert result.status=='exact-symbolic'
    assert result.details['outer_radius']=='1' and result.details['radius_estimate']==1
    assert result.provenance.context==COMPLEX_CONTEXT
    assert p.objects==original and len(p.analytic_germs)==1
    germ=next(iter(p.analytic_germs.values()))
    assert germ.coefficients[2].power==2
    assert 'no certified' in germ.error_model


def test_laurent_principal_part_and_punctured_domain():
    p=project('f(z)=1/(z*(z-1))')
    result=run(p,'f','laurent',order=6)
    values=coefficients(result)
    assert values[-1]=='-1' and all(values[i]=='-1' for i in range(6))
    assert result.details['outer_radius']=='1' and result.details['inner_radius']=='0'
    assert any('z' in condition for condition in result.exceptional_sets)
    with pytest.raises(ValueError,match='exclusion'):
        run(p,'f','taylor',order=6)


def test_removable_holes_are_not_silently_filled():
    p=project('f(z)=z/z')
    with pytest.raises(ValueError,match='exclusion'):
        run(p,'f','taylor')
    result=run(p,'f','laurent',order=6)
    assert coefficients(result)[0]=='1'
    assert result.exceptional_sets==('z = 0',)
    transformed=run(p,'f','builtin:simplify')
    assert transformed.details['expression']=='1'
    assert transformed.exceptional_sets==('z = 0',)


@pytest.mark.parametrize('definition',['f(z)=z^(1/2)','f(z)=log(z)','f(z)=exp(1/z)'])
def test_branched_puiseux_or_essential_templates_not_mislabeled(definition):
    p=project(definition)
    original=p.objects.copy()
    with pytest.raises(ValueError):
        run(p,'f','laurent')
    assert p.objects==original and not p.analysis_records and not p.analytic_germs


def test_elementary_entire_series_and_its_unbounded_template():
    p=project('f(z)=exp(z)')
    result=run(p,'f','taylor',order=7)
    assert coefficients(result)[6]=='1/720'
    assert result.details['outer_radius']=='infinity'
    with pytest.raises(ValueError,match='rational'):
        run(p,'f','continue')


def test_cauchy_coefficients_are_numeric_and_agree_with_exact_coefficients():
    p=project('f(z)=1/(1+z^2)')
    result=run(p,'f','cauchy',order=8,digits=35)
    assert result.status=='numerically-computed'
    for row in result.details['cauchy']['coefficients']:
        value=complex(row['coefficient'].replace(' ',''))
        n=row['power']
        assert abs(value-((-1)**(n//2) if n%2==0 else 0))<1e-25
    assert result.details['cauchy']['orientation']=='positive/counterclockwise'
    assert 'not a certified' in result.details['cauchy']['error_model']
    with pytest.raises(ValueError,match='safely inside'):
        run(p,'f','cauchy',radius='1')


def test_continuation_to_two_uses_overlapping_disks_and_records_approximation():
    p=project('f(z)=1/(1+z^2)')
    result=run(p,'f','continue',order=24,digits=35,path='0,0;2,0')
    value=result.details['continuation']
    assert result.status=='numerically-computed'
    assert abs(complex(value['value'].replace(' ',''))-0.2)<1e-14
    assert mp.mpf(value['reference_absolute_difference'])<mp.mpf('1e-14')
    assert len(value['steps'])>1
    assert 'not a certified' in value['error_model']
    for step in value['steps']:
        assert mp.mpf(step['step_length'])<=mp.mpf(step['radius_estimate'])*mp.mpf('0.301')
        assert len(step['center_coordinates'])==2 and len(step['from_coordinates'])==2
    assert 'no exact-value resets' in value['method']
    assert value['path']==['0','2']


def test_taylor_transport_does_not_reinitialize_at_exact_source_values(monkeypatch):
    import mathsandbox.analysis.continuation as module
    from mathsandbox.analysis.series import rational_coefficients
    p=project('f(z)=1/(1+z^2)')
    compiler=Compiler(p,'f')
    def perturbed(expression,z,c,n):
        original=rational_coefficients(expression,z,c,n)
        return rational_coefficients(expression,z,c,n,seed=original[0]+sp.Rational(1,10))
    monkeypatch.setattr(module,'rational_coefficients',perturbed)
    result=transport(compiler,sp.Integer(0),24,35,'0,0;2,0')
    # The differential invariant carries the perturbed germ: 1.1/(1+z^2) at 2.
    assert abs(complex(result['value'].replace(' ',''))-0.22)<1e-14
    assert abs(complex(result['reference_value'].replace(' ',''))-0.2)<1e-14


@pytest.mark.parametrize('path',['0,0;0,2','1,0;2,0','0,0;bad,0'])
def test_singular_or_malformed_paths_are_rejected_atomically(path):
    p=project('f(z)=1/(1+z^2)')
    with pytest.raises(ValueError):
        run(p,'f','continue',path=path)
    assert not p.analytic_germs and not p.analysis_records


def test_a_detour_path_preserves_path_and_reaches_endpoint():
    p=project('f(z)=1/(1+z^2)')
    result=run(p,'f','continue',order=24,path='0,0;1,1;2,0')
    assert result.details['continuation']['path']==['0','1 + I','2']
    assert mp.mpf(result.details['continuation']['reference_absolute_difference'])<mp.mpf('1e-12')


def test_parameter_pde_demo_is_conditional_and_does_not_divide_by_x():
    p=project('F(x,y,a,b)=y^2-a*x^3+b*x',Context())
    result=run(p,'F','parameter-constraint')
    assert result.status=='conditional-symbolic-identity'
    assert result.details['constraint']=='x**2*y_b + y_a = 0'
    assert result.details['checked_syzygy_residual']=='0'
    assert 'y != 0' in result.assumptions
    assert not any('x != 0' in condition for condition in result.assumptions)
    assert 'necessary' in result.reconstruction
    assert result.details['source_equation'].endswith('= 0')
    assert result.provenance.source_id==p.names['F']


def test_parameter_constraint_common_factor_can_vanish_without_extra_division():
    p=project('F(x,y,a,b)=y*(y-a*x+b)',Context())
    result=run(p,'F','parameter-constraint')
    assert result.details['checked_syzygy_residual']=='0'
    assert not any(condition=='y != 0' for condition in result.assumptions)


@pytest.mark.parametrize('definition',['F(x,y,a,b)=x+a+b','F(x,y,a,b)=y-a/x+b'])
def test_degenerate_or_rational_implicit_sources_are_not_certified(definition):
    p=project(definition,Context())
    with pytest.raises(ValueError):
        run(p,'F','parameter-constraint')


def test_parameter_derivative_names_do_not_capture_source_parameters():
    p=project('F(x,y,a,b,y_a)=y^2-a*x+b+y_a',Context())
    result=run(p,'F','parameter-constraint')
    assert 'D[y,a]' in result.details['derivative_bindings'].values()


def test_transform_registry_and_custom_rewrites_keep_exactness_distinct():
    p=project('f(z)=(z+1)^2')
    p.register_rewrite('custom:expand','(x+1)^2','x^2+2*x+1')
    exact=run(p,'f','custom:expand')
    assert exact.status=='exact-symbolic'
    p.register_rewrite('custom:guess','(x+1)^2','x^2')
    guessed=run(p,'f','custom:guess')
    assert guessed.status=='exploratory' and 'not certified' in guessed.details['verification']
    assert p.objects[p.names['f']].original_definition=='f(z)=(z+1)^2'
    derivative=run(p,'f','builtin:differentiate')
    assert derivative.details['expression']=='2*z + 2'
    assert 'integration constant' in derivative.reconstruction


def test_branch_conditions_survive_symbolic_transforms():
    p=project('f(z)=log(z)')
    result=run(p,'f','builtin:differentiate')
    assert result.details['expression']=='1/z'
    assert any('cut' in condition for condition in result.exceptional_sets)


def test_new_analysis_backend_rejects_unlicensed_context_and_custom_products():
    p=project('f(z)=z^2',replace(COMPLEX_CONTEXT,axioms=('inconsistent',)))
    with pytest.raises(ValueError,match='licensed'):
        run(p,'f','taylor')
    p=Project();p.registry.register(OperatorDefinition('custom:star','star',2));p.define('f(z)=star(z,z)',COMPLEX_CONTEXT)
    with pytest.raises(ValueError,match='Custom'):
        run(p,'f','taylor')
    p=project('f(x)=x^2',Context())
    with pytest.raises(ValueError,match='complex context'):
        run(p,'f','taylor')


def test_germ_and_record_roundtrip_staleness_and_loaded_coefficients_not_trusted():
    p=project('f(z)=1/(1+z^2)')
    run(p,'f','taylor',order=24)
    p.register_rewrite('custom:identity','x','x')
    restored=loads(dumps(p))
    assert restored.analytic_germs==p.analytic_germs
    assert restored.analysis_records==p.analysis_records
    assert restored.transform_registry.definitions==p.transform_registry.definitions
    data=json.loads(dumps(p))
    data['analytic_germs'][0]['coefficients'][0]['value']={'kind':'integer','value':'999','args':[],'conventions':[]}
    forged=loads(json.dumps(data))
    germ_id=next(iter(forged.analytic_germs))
    actual=continue_germ(forged,germ_id,'0,0;2,0')
    assert abs(complex(actual.details['continuation']['value'].replace(' ',''))-0.2)<1e-14
    forged.define('f(z)=1/(2+z^2)')
    assert not current(forged,forged.analytic_germs[germ_id].provenance)
    with pytest.raises(ValueError,match='stale'):
        continue_germ(forged,germ_id,'0,0;2,0')


def test_dependency_edits_invalidate_germ_provenance():
    p=project('f(z)=z^2')
    p.define('g(z)=1/(1+f(z))',COMPLEX_CONTEXT)
    record=run(p,'g','taylor',order=8)
    assert current(p,record.provenance)
    p.define('f(z)=z^3')
    assert not current(p,record.provenance)
    updated=run(p,'g','taylor',order=8)
    assert coefficients(updated)[2]=='0' and coefficients(updated)[3]=='-1'


def test_historical_analysis_details_are_detached_from_returned_results():
    p=project('f(z)=1/(1+z^2)')
    result=run(p,'f','taylor',order=8)
    result.details['coefficients'][0]['coefficient']='forged'
    assert p.analysis_records[0].details['coefficients'][0]['coefficient']=='1'


@pytest.mark.parametrize('options',[{'order':1000},{'digits':1},{'center_real':'__import__("os")'},{'center_imag':'nan'}])
def test_analysis_bounds_and_unsafe_inputs_fail_without_mutation(options):
    p=project('f(z)=1/(1+z^2)')
    with pytest.raises(ValueError):
        run(p,'f','taylor',**options)
    assert not p.analytic_germs and not p.analysis_records


def test_analysis_timeout():
    p=project('f(z)=z^2')
    with pytest.raises(ValueError,match='timed out'):
        run(p,'f','taylor',timeout=0)


def test_workbench_analysis_history_settings_and_keep_unevaluated():
    session=Workbench();session.choose_example('series')
    result=session.analyse({'name':'f',**session.analysis_settings,'order':24})
    assert result['record']['status']=='numerically-computed'
    restored=Workbench();restored.restore(session.export())
    assert restored.analysis_settings==session.analysis_settings
    assert restored.project.analytic_germs==session.project.analytic_germs
    assert restored.project.analysis_records==session.project.analysis_records
    restored.view['mode']='unevaluated'
    with pytest.raises(ValueError,match='disables'):
        restored.analyse({'name':'f'})
    session.choose_example('implicit')
    result=session.analyse({'name':'F',**session.analysis_settings})
    assert result['record']['details']['constraint']=='x**2*y_b + y_a = 0'


def test_builtin_transformation_tampering_and_bad_analysis_import_rejected():
    p=project('f(z)=z^2')
    data=json.loads(dumps(p));data['transform_registry'][0]['description']='Other meaning'
    with pytest.raises(ValueError,match='Modified builtin'):
        loads(json.dumps(data))
    session=Workbench();data=json.loads(session.export());data['workbench']['analysis_settings']['order']=1000
    before=dumps(session.project)
    with pytest.raises(ValueError):
        session.restore(json.dumps(data))
    assert dumps(session.project)==before


def test_laurent_complex_center_retains_integer_powers_and_correct_annulus():
    p=project('f(z)=1/(1+z^2)')
    result=run(p,'f','laurent',center_imag='1',order=6)
    assert coefficients(result)[-1]=='-I/2'
    assert coefficients(result)[0]=='1/4'
    assert result.details['outer_radius']=='2'


def test_positive_rewrite_conditions_do_not_leak_into_complex_context():
    positive=project('f(x)=(x^2)^(1/2)',Context(domain='PositiveReals'))
    positive.register_rewrite('custom:root','(x^2)^(1/2)','x')
    assert run(positive,'f','custom:root').status=='exact-symbolic'
    complex_project=project('f(z)=(z^2)^(1/2)')
    complex_project.register_rewrite('custom:root','(x^2)^(1/2)','x')
    result=run(complex_project,'f','custom:root')
    assert result.status=='exploratory'
    assert any('cut' in condition for condition in result.exceptional_sets)


def test_analysis_settings_can_be_saved_without_running_backend():
    session=Workbench()
    settings={**session.analysis_settings,'order':12,'method':'laurent'}
    session.set_analysis_settings(settings)
    assert not session.project.analysis_records
    restored=Workbench();restored.restore(session.export())
    assert restored.analysis_settings['order']==12 and restored.analysis_settings['method']=='laurent'
