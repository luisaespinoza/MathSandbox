from dataclasses import asdict, replace
import json
import math
import mpmath as mp
import pytest
import sympy as sp
from mathsandbox import Context, OperatorDefinition, Project
from mathsandbox.adapters.complex_numeric import COMPLEX_CONTEXT, ComplexEvaluator
from mathsandbox.adapters.padic import RATIONAL_CONTEXT, RationalEvaluator, rational, describe, valuation
from mathsandbox.storage.json_project import dumps
from mathsandbox.visualization.complex_views import sphere, color, sample_complex
from mathsandbox.visualization.geometry import GeometrySettings, compute_geometry
from mathsandbox.visualization.sampling import PlotSettings
from mathsandbox.ui.workbench import Workbench


def project(definition, context):
    p = Project()
    p.define(definition, context)
    return p


@pytest.mark.parametrize('z', [0, 1, -1, 1j, -1j, 2+3j, 1000000])
def test_sphere_projection_is_unit_length_and_invertible(z):
    with mp.workdps(40):
        x,y,t = sphere(z)
        assert x*x+y*y+t*t == pytest.approx(1, abs=1e-14)
        if t != 1:
            recovered = complex(x,y)/(1-t)
            assert recovered == pytest.approx(complex(z), rel=1e-4, abs=1e-12)
    assert sphere(None) == [0,0,1]
    assert sphere(0) == [0,0,-1]
    with pytest.raises(ValueError):
        sphere(mp.inf)


def test_domain_colors_encode_phase_modulus_and_zero():
    assert color(mp.mpc(0)) == [0,0,0,255]
    assert color(mp.mpc(1)) != color(mp.mpc(-1))
    assert color(mp.mpc(1j)) != color(mp.mpc(-1j))
    assert max(color(mp.mpc(10))[:3]) > max(color(mp.mpc('0.1'))[:3])


def test_complex_arithmetic_is_pointwise_without_symbolic_cancellation():
    p = project('f(z)=z/z', COMPLEX_CONTEXT)
    evaluator = ComplexEvaluator(p, 'f')
    assert evaluator.at(mp.mpc(2,3)) == 1
    with pytest.raises(ValueError):
        evaluator.at(0)
    p.define('g(z)=I*z', COMPLEX_CONTEXT)
    assert ComplexEvaluator(p, 'g').at(2) == 2j
    assert p.evaluate('g').status == 'unevaluated'  # Real CAS gate is still closed.


def test_complex_context_and_custom_operators_cannot_be_silently_extended():
    p = project('f(x)=x^2', Context())
    with pytest.raises(ValueError, match='explicit'):
        ComplexEvaluator(p, 'f')
    p.define('g(z)=f(z)', COMPLEX_CONTEXT)
    with pytest.raises(ValueError, match='matching'):
        ComplexEvaluator(p, 'g').at(1j)
    p.registry.register(OperatorDefinition('custom:star','star',2))
    p.define('h(z)=star(z,I)', COMPLEX_CONTEXT)
    with pytest.raises(ValueError, match='Custom'):
        ComplexEvaluator(p, 'h').at(1)
    p.define('bad(z)=log(z)', replace(COMPLEX_CONTEXT, branches=('multivalued',)))
    with pytest.raises(ValueError, match='principal'):
        ComplexEvaluator(p, 'bad')


def test_principal_log_cut_is_masked_and_boundary_value_is_labeled():
    p = project('f(z)=log(z)', COMPLEX_CONTEXT)
    original = dumps(p)
    settings = PlotSettings(lower='-2', upper='2')
    geometry = GeometrySettings(geometry='domain-coloring', resolution=21)
    result = sample_complex(p,'f',settings,geometry,coordinate='-1')
    plot = result['plot']
    assert len(plot['rgba']) == len(plot['height']) == 21
    assert all(plot['rgba'][10][i][3] == 0 for i in range(11))
    assert plot['rgba'][10][-1][3] == 255
    assert result['point']['branch_warning']
    assert plot['warnings'] and plot['conventions']['branch'].startswith('principal')
    assert dumps(p) == original


def test_shifted_cut_crossing_between_grid_rows_is_not_bridged():
    p = project('f(z)=log(z-I/10)', COMPLEX_CONTEXT)
    result = sample_complex(p,'f',PlotSettings(lower='-2',upper='2'),GeometrySettings(geometry='complex-magnitude', resolution=21))
    plot = result['plot']
    # The cut Im(z)=0.1 lies between rows 0 and 0.2; both sides are masked for Re<0.
    assert plot['height'][10][0] is None and plot['height'][11][0] is None
    assert any('Cut-crossing' in message for message in plot['warnings'])


def test_integer_powers_do_not_invent_branch_cuts():
    p = project('f(z)=z^2', COMPLEX_CONTEXT)
    result = sample_complex(p,'f',PlotSettings(lower='-2',upper='2'),GeometrySettings(geometry='complex-compare', resolution=21))
    assert all(pixel[3] == 255 for row in result['plot']['rgba'] for pixel in row)
    assert not result['plot']['warnings']


def test_poles_are_omitted_without_claiming_a_singularity_certificate():
    p = project('f(z)=1/(z^2+1)', COMPLEX_CONTEXT)
    result = sample_complex(p,'f',PlotSettings(lower='-2',upper='2'),GeometrySettings(geometry='complex-compare', resolution=21))
    plot = result['plot']
    assert plot['height'][5][10] is None and plot['height'][15][10] is None
    assert plot['infinity'] == [0,0,1]
    assert 'not a detected pole' in plot['conventions']['sphere']
    assert len(plot['sphere']) < 441


def test_log_height_preserves_values_and_handles_display_overflow():
    p = project('f(z)=exp(1000*z)', COMPLEX_CONTEXT)
    settings = PlotSettings(lower='1',upper='2')
    geometry = GeometrySettings(geometry='complex-magnitude', resolution=21, imaginary_lower='-1', imaginary_upper='1')
    linear = sample_complex(p,'f',settings,geometry)['plot']
    logarithmic = sample_complex(p,'f',settings,replace(geometry,height_scale='log1p'))['plot']
    assert linear['height'][10][10] is None
    assert logarithmic['height'][10][10] == pytest.approx(1500)
    assert linear['hover'][10][10] == logarithmic['hover'][10][10]
    assert any('overflows' in message for message in linear['warnings'])


@pytest.mark.parametrize('text,v,norm', [('125',3,'1/125'),('-125',3,'1/125'),('1/25',-2,'25'),('7/15',-1,'5'),('0','infinity','0')])
def test_exact_valuation_and_norm(text,v,norm):
    data = describe(rational(text),5,4)
    assert data['valuation'] == v and data['norm'] == norm
    assert data['rational'] == text


def test_residue_digits_and_tree_containment_are_exact():
    for text in ('1/3', '-1/25','7/15','125','0'):
        q = rational(text)
        data = describe(q,5,6)
        assert data['unit_residue'] == sum(digit*5**i for i,digit in enumerate(data['digits']))
        if q:
            unit = sp.Rational(data['unit_part'])
            residual = unit-data['unit_residue']
            assert residual == 0 or valuation(residual,5) >= 6
            assert q == sp.Integer(5)**data['valuation']*unit
        else:
            assert data['unit_part'] is None
        by_id = {node['id']:node for node in data['nodes']}
        assert len(data['nodes']) == 1+5*6
        for node in data['nodes'][1:]:
            parent = by_id[node['parent']]
            assert node['residue'] % parent['modulus'] == parent['residue']
        assert sum(node['selected'] for node in data['nodes']) == 7


def test_norm_is_multiplicative_for_exact_rationals():
    a,b = rational('7/15'), rational('-25/3')
    norm = lambda q: sp.Rational(describe(q,5,3)['norm'])
    assert norm(a*b) == norm(a)*norm(b)
    assert describe(rational('1/3'),5,4)['digits'] == [2,3,1,3]


@pytest.mark.parametrize('bad', ['0.1','1e-3','sin(1)','1/0','NaN','Infinity','__import__("os")'])
def test_padic_input_never_uses_float_or_executable_parsing(bad):
    with pytest.raises(ValueError):
        rational(bad)


@pytest.mark.parametrize('prime', [1,4,25,101,True,5.0])
def test_nonprime_or_out_of_budget_prime_rejected(prime):
    with pytest.raises(ValueError):
        describe(rational('125'),prime,4)


def test_exact_rational_adapter_preserves_domain_exclusions_and_contexts():
    p = project('f(x)=x/x', RATIONAL_CONTEXT)
    evaluator = RationalEvaluator(p,'f')
    assert evaluator.at(rational('2')) == 1
    with pytest.raises(ValueError):
        evaluator.at(rational('0'))
    p.define('g(x)=sin(x)',RATIONAL_CONTEXT)
    with pytest.raises(ValueError, match='rational arithmetic'):
        RationalEvaluator(p,'g').at(rational('0'))
    p.define('real(x)=x',Context())
    with pytest.raises(ValueError, match='explicit'):
        RationalEvaluator(p,'real')
    p.define('call(x)=real(x)',RATIONAL_CONTEXT)
    with pytest.raises(ValueError, match='matching'):
        RationalEvaluator(p,'call').at(rational('1'))


def test_exact_rational_function_data_tracks_edits_and_not_euclidean_scaling():
    p = project('f(x)=x^2+1',RATIONAL_CONTEXT)
    settings,geometry = PlotSettings(),GeometrySettings(geometry='padic-tree')
    first = compute_geometry(p,'f',settings,geometry,'2')
    assert first['point']['status'] == 'exact-rational' and first['point']['value'] == '5'
    assert first['plot']['valuation'] == 1
    assert 'ultrametric' in first['plot']['conventions']['topology']
    p.define('f(x)=x^2+21')
    second = compute_geometry(p,'f',settings,geometry,'2')
    assert second['plot']['valuation'] == 2
    assert second['plot']['source_revision'] > first['plot']['source_revision']


@pytest.mark.parametrize('geometry', [GeometrySettings(geometry='unknown'),GeometrySettings(geometry='complex-compare',resolution=22),GeometrySettings(geometry='complex-compare',resolution=1001),GeometrySettings(geometry='complex-compare',imaginary_lower='2',imaginary_upper='1'),GeometrySettings(geometry='padic-tree',padic_digits=100),GeometrySettings(geometry='padic-tree',prime=6)])
def test_geometry_validation_is_bounded(geometry):
    with pytest.raises(ValueError):
        geometry.validate(PlotSettings())


def test_advanced_view_settings_roundtrip_and_invalid_import_is_atomic():
    session = Workbench()
    session.choose_example('complex')
    session.view.update(geometry='riemann-sphere',resolution=21,height_scale='log1p',imag_coordinate='1/2')
    data = session.export()
    restored = Workbench()
    restored.restore(data)
    assert restored.view == session.view
    assert restored.project.objects == session.project.objects
    original = dumps(restored.project)
    invalid = json.loads(data)
    invalid['workbench']['view']['resolution'] = 1000
    with pytest.raises(ValueError):
        restored.restore(json.dumps(invalid))
    assert dumps(restored.project) == original
    # A1/A2 view records still migrate into the real view.
    legacy = Workbench()
    old = json.loads(legacy.export())
    old['workbench']['schema_version'] = 1
    for field in asdict(GeometrySettings()):
        old['workbench']['view'].pop(field,None)
    restored.restore(json.dumps(old))
    assert restored.view['geometry'] == 'real'


def test_explicit_number_universe_changes_are_historical_edits():
    session = Workbench()
    obj = session.project.objects[session.project.names['f']]
    session.set_domain('f','Complexes')
    changed = session.project.objects[obj.id]
    assert changed.context == COMPLEX_CONTEXT
    assert session.project.history[-1] == obj
    session.set_domain('f','Rationals')
    assert session.project.objects[obj.id].context == RATIONAL_CONTEXT
    session.set_domain('f','Reals')
    assert session.project.objects[obj.id].context == Context()


def test_geometry_worker_timeout():
    p = project('f(z)=z^2',COMPLEX_CONTEXT)
    with pytest.raises(ValueError, match='timed out'):
        compute_geometry(p,'f',PlotSettings(),GeometrySettings(geometry='domain-coloring'),'1',timeout=0)


@pytest.mark.parametrize('example,kind', [('complex','complex'),('padic','padic')])
def test_workbench_examples_are_renderable_and_respect_unevaluated_mode(example,kind):
    session = Workbench()
    session.choose_example(example)
    view = {**session.view,'resolution':21}
    result = session.render(view)
    assert result['plot']['kind'] == kind
    assert result['plot']['context'] == asdict(session.project.objects[session.project.names['f']].context)
    assert result['point']
    if kind == 'padic':
        assert result['plot']['valuation'] == 3
    kept = session.render({**view,'mode':'unevaluated'})
    assert kept['plot'] is None and kept['point'] is None


def test_complex_phase_palette_is_explicit_and_cyclic():
    p = project('f(z)=z',COMPLEX_CONTEXT)
    result = sample_complex(p,'f',PlotSettings(lower='-1',upper='1'),GeometrySettings(geometry='domain-coloring',resolution=21))
    palette = result['plot']['phase_colorscale']
    assert palette[0] == [0,'rgb(255,0,0)']
    assert palette[-1] == [1,'rgb(255,0,0)']
    assert palette[3] == [0.5,'rgb(0,255,255)']


def test_advanced_function_calls_are_reactive_and_keep_source_provenance():
    p = project('f(z)=z^2',COMPLEX_CONTEXT)
    p.define('g(z)=f(z)+I',COMPLEX_CONTEXT)
    original = dumps(p)
    first = sample_complex(p,'g',PlotSettings(lower='-1',upper='1'),GeometrySettings(geometry='domain-coloring',resolution=21),'1')
    assert '(1.0 + 1.0j)' == first['point']['value']
    assert dumps(p) == original
    p.define('f(z)=z^3+1')
    second = sample_complex(p,'g',PlotSettings(lower='-1',upper='1'),GeometrySettings(geometry='domain-coloring',resolution=21),'1')
    assert '(2.0 + 1.0j)' == second['point']['value']
    assert first['plot']['dependency_revisions'] != second['plot']['dependency_revisions']


def test_view_provenance_and_exact_outcomes_survive_save_without_becoming_cache():
    session=Workbench()
    session.choose_example('padic')
    result=session.render(session.view)
    record=session.view_records[-1]
    assert record['norm']=='1/125' and record['valuation']==3
    assert record['backend']=='SymPy' and record['backend_version']==sp.__version__
    assert record['context']==json.loads(json.dumps(asdict(RATIONAL_CONTEXT)))
    assert record['point']['status']=='exact-rational'
    assert record['absolute_precision']==7
    restored=Workbench()
    restored.restore(session.export())
    assert restored.view_records==session.view_records
    data=json.loads(session.export())
    data['workbench']['view_records'][-1]['point']['value']='forged'
    restored.restore(json.dumps(data))
    actual=restored.render(restored.view)
    assert actual['point']['value']=='125'
    assert restored.view_records[-1]['point']['value']=='125'
    assert restored.view_records[0]['point']['value']=='forged'  # Historical records are never proof certificates.


def test_complex_view_provenance_is_preserved_and_detached_from_returned_data():
    session=Workbench()
    session.choose_example('complex')
    result=session.render({**session.view,'resolution':21})
    before=json.dumps(session.view_records,sort_keys=True)
    result['plot']['context']['branches']=['multivalued']
    assert json.dumps(session.view_records,sort_keys=True)==before
    restored=Workbench()
    restored.restore(session.export())
    assert restored.view_records==session.view_records
    assert restored.view_records[-1]['conventions']['branch'].startswith('principal')
    assert restored.view_records[-1]['status']=='numerically-sampled'


def test_maximum_residue_tree_stays_finite_and_json_integers_are_exact():
    data=describe(rational('1/3'),97,8)
    assert len(data['nodes'])==777
    assert data['modulus'] < 2**53
    assert data['absolute_precision']==8
    data=describe(rational('1/25'),5,4)
    assert data['absolute_precision']==2
