from dataclasses import asdict
import json
import mpmath as mp
import pytest
import sympy as sp
from mathsandbox import Context, ConstructionDefinition, OperatorDefinition, Project
from mathsandbox.adapters.numeric import point
from mathsandbox.storage.json_project import dumps, loads

POSITIVE = Context(domain="PositiveReals")


def project(text, context=None):
    p = Project()
    p.define(text, context)
    return p


def equivalent(p, name, expected):
    result = p.evaluate(name)
    assert result.status == "exact", result.provenance.diagnostic
    actual = p.to_sympy(name)
    x = sp.Symbol("x", positive=True)
    actual = actual.xreplace({s: x for s in actual.free_symbols})
    assert sp.simplify(actual-expected(x)) == 0
    return result


@pytest.mark.parametrize("definition,value", [
    ('f(x)=Tower(2,(k,1,0),1)', 1),
    ('f(x)=Tower(2,(k,1,1),1)', 2),
    ('f(x)=Tower(2,(k,1,2),1)', 4),
    ('f(x)=Tower(2,(k,1,3),1)', 16),
    ('f(x)=Tower(2,(k,1,4),1)', 65536),
    ('f(x)=Tower(k+1,(k,1,3),1)', 2**81),
    ('f(x)=IndexedFold(k+1,(k,1,3),"pow","left",1)', 4096),
    ('f(x)=IndexedFold(k,(k,1,5),"add","left",0)', 15),
    ('f(x)=IndexedFold(k,(k,1,5),"mul","right",1)', 120),
    ('f(x)=IndexedFold(k,(k,3,1),"add","right",7)', 7),
])
def test_finite_folds_and_explicit_boundary_conventions(definition, value):
    p = project(definition)
    result = equivalent(p, "f", lambda x: value)
    assert any(rule.startswith("fold:") for rule in result.provenance.rules)


def test_fold_capture_avoidance_and_named_dependencies():
    p = project('f(x)=x+1')
    p.define('g(k)=Tower(f(k),(k,1,3),1)+k')
    equivalent(p, "g", lambda x: 2**81+x)
    p.define('f(x)=2')
    assert p.names["g"] not in p.representations
    equivalent(p, "g", lambda x: 16+x)
    p.define('nested(x)=IndexedFold(IndexedFold(k,(k,1,2),"add","left",0)+k,(k,1,2),"add","left",0)')
    equivalent(p, "nested", lambda x: 9)


@pytest.mark.parametrize("definition", [
    'f(n)=Tower(2,(k,1,n),1)',
    'f(x)=Tower(2,(k,1,3/2),1)',
    'f(x)=Tower(2,(k,1,5),1)',
    'f(x)=IndexedFold(k,(k,1,100),"add","left",0)',
])
def test_symbolic_noninteger_and_resource_limited_folds_remain_formal(definition):
    p = project(definition)
    original = p.objects[p.names["f"]].expression
    result = p.evaluate("f")
    assert result.status == "unevaluated"
    assert result.expression == original
    assert result.provenance.diagnostic


def test_custom_fold_never_becomes_builtin_multiplication():
    p = Project()
    p.registry.register(OperatorDefinition("custom:star", "star", 2, semantics="right-projection"))
    p.define('f(x)=IndexedFold(k,(k,1,3),"star","right",0)')
    assert p.evaluate("f").status == "unevaluated"
    restored = loads(dumps(p))
    assert restored.objects == p.objects
    assert restored.evaluate("f").expression.value == "custom:star"


def test_fractional_power_integral_exact_with_context_and_rule():
    p = project('f(x)=FractionalIntegral(x^2,(x,0),1/2,"riemann-liouville")', POSITIVE)
    result = equivalent(p, "f", lambda x: 16*x**sp.Rational(5,2)/(15*sp.sqrt(sp.pi)))
    assert result.provenance.context == POSITIVE
    assert any("alpha>0,beta>-1,x>0" in rule for rule in result.provenance.rules)
    assert float(point(p, "f", "2").value) == pytest.approx(float(16*2**mp.mpf("2.5")/(15*mp.sqrt(mp.pi))))
    with pytest.raises(ValueError, match="positive"):
        point(p, "f", "0")


def test_riemann_liouville_and_caputo_have_different_initial_conditions():
    rl = project('f(x)=FractionalDerivative(1,(x,0),1/2,"riemann-liouville")', POSITIVE)
    caputo = project('f(x)=FractionalDerivative(1,(x,0),1/2,"caputo")', POSITIVE)
    equivalent(rl, "f", lambda x: 1/sp.sqrt(sp.pi*x))
    equivalent(caputo, "f", lambda x: 0)
    assert rl.evaluate("f").provenance.rules != caputo.evaluate("f").provenance.rules
    p = project('f(x)=FractionalDerivative(x,(x,0),3/2,"caputo")', POSITIVE)
    equivalent(p, "f", lambda x: 0)


@pytest.mark.parametrize("formula,context", [
    ('FractionalIntegral(x^2,(x,0),1/2,"riemann-liouville")', Context()),
    ('FractionalIntegral(x^2,(x,1),1/2,"riemann-liouville")', POSITIVE),
    ('FractionalIntegral(x^2,(x,0),-1/2,"riemann-liouville")', POSITIVE),
    ('FractionalIntegral(sin(x),(x,0),1/2,"riemann-liouville")', POSITIVE),
    ('FractionalIntegral(x^(-2),(x,0),1/2,"riemann-liouville")', POSITIVE),
    ('FractionalDerivative(x^(1/2),(x,0),3/2,"caputo")', POSITIVE),
    ('FractionalIntegral(x,(x,0),I,"riemann-liouville")', POSITIVE),
    ('FractionalIntegral(x,(x,0),1/2,"other-definition")', POSITIVE),
])
def test_fractional_obligations_and_unsupported_definitions_preserved(formula, context):
    p = project("f(x)="+formula, context)
    original = p.objects[p.names["f"]].expression
    result = p.evaluate("f")
    assert result.status == "unevaluated"
    assert result.expression == original
    assert result.provenance.context == context
    assert result.provenance.diagnostic


def test_fractional_symbolic_order_unevaluated_without_positivity():
    p = project('f(x,a)=FractionalIntegral(x^2,(x,0),a,"riemann-liouville")')
    assert p.evaluate("f").status == "unevaluated"


def test_half_iterate_and_composition_law_are_exact():
    p = project("f(x)=x^2")
    p.define('half(x)=Iterate(f,1/2,x,"positive-power")', POSITIVE)
    p.define("twice(x)=half(half(x))", POSITIVE)
    p.define('zero(x)=Iterate(f,0,x,"positive-power")', POSITIVE)
    equivalent(p, "half", lambda x: x**sp.sqrt(2))
    result = equivalent(p, "twice", lambda x: x**2)
    equivalent(p, "zero", lambda x: x)
    assert any("chosen-positive-power-family" in rule for rule in result.provenance.rules)
    assert set(p.objects[p.names["half"]].dependencies) == {p.names["f"]}
    p.define("f(x)=x^3")
    assert p.names["half"] not in p.representations and p.names["twice"] not in p.representations
    equivalent(p, "twice", lambda x: x**3)


@pytest.mark.parametrize("base,family,time,expected", [
    ("x+3", "translation", "1/2", lambda x: x+sp.Rational(3,2)),
    ("4*x", "positive-scaling", "1/2", lambda x: 2*x),
    ("x+1", "integer", "3", lambda x: x+3),
])
def test_other_recognized_iteration_families(base, family, time, expected):
    p = project("f(x)="+base)
    p.define(f'g(x)=Iterate(f,{time},x,"{family}")')
    equivalent(p, "g", expected)


@pytest.mark.parametrize("base,family,time,context", [
    ("x^2", "positive-power", "1/2", Context()),
    ("sin(x)", "positive-power", "1/2", POSITIVE),
    ("x^2", "integer", "1/2", POSITIVE),
    ("x^2", "positive-power", "I", POSITIVE),
    ("x^2", "unselected-extension", "1/2", POSITIVE),
    ("-2*x", "positive-scaling", "1/2", Context()),
    ("x^2", "integer", "-1", POSITIVE),
])
def test_iteration_extensions_not_invented(base, family, time, context):
    p = project("f(x)="+base)
    p.define(f'g(x)=Iterate(f,{time},x,"{family}")', context)
    original = p.objects[p.names["g"]].expression
    result = p.evaluate("g")
    assert result.status == "unevaluated" and result.expression == original
    assert result.provenance.diagnostic


def test_positive_callee_domain_cannot_leak_to_negative_argument():
    p = project("f(x)=x^(1/2)", POSITIVE)
    p.define("g(x)=f(-1)")
    assert p.evaluate("g").status == "unevaluated"
    p.define("h(x)=f(4)")
    equivalent(p, "h", lambda x: 2)


def test_a2_json_roundtrip_and_formal_extension_registry():
    p = project("f(x)=x^2")
    p.define('half(x)=Iterate(f,1/2,x,"positive-power")', POSITIVE)
    p.define('tower(x)=Tower(x,(k,1,3),1)', POSITIVE)
    p.define('integral(x)=FractionalIntegral(x^2,(x,0),1/2,"riemann-liouville")', POSITIVE)
    p.constructions.register(ConstructionDefinition("custom:abel", "iteration", "User-specified Abel construction without evaluator"))
    p.define('formal(x)=Iterate(f,1/2,x,"custom:abel")', POSITIVE)
    for name in p.names:
        p.evaluate(name)
    restored = loads(dumps(p))
    assert restored.objects == p.objects
    assert restored.transformations == p.transformations
    assert restored.constructions.definitions == p.constructions.definitions
    equivalent(restored, "half", lambda x: x**sp.sqrt(2))
    assert restored.evaluate("formal").status == "unevaluated"
    data = json.loads(dumps(p))
    data["objects"][2]["expression"]["conventions"][0][1] = "ambiguous"
    with pytest.raises(ValueError, match="conventions"):
        loads(json.dumps(data))


def test_resource_guard_applies_after_composition_and_iteration():
    p = project("f(x)=x^2")
    p.define('huge(x)=Iterate(f,30,2,"integer")')
    result = p.evaluate("huge")
    assert result.status == "unevaluated" and "budget" in result.provenance.diagnostic
    p.define('large(x)=Iterate(f,100000,2,"positive-power")', POSITIVE)
    assert p.evaluate("large").status == "unevaluated"
    p.define('large_order(x)=FractionalIntegral(x,(x,0),1000000,"riemann-liouville")', POSITIVE)
    assert p.evaluate("large_order").status == "unevaluated"


def test_complex_constants_are_formal_in_a_real_context():
    p = project("f(x)=I")
    assert p.evaluate("f").status == "unevaluated"
    with pytest.raises(ValueError, match="Nonfinite or nonreal"):
        point(p, "f", "1")


def test_construction_metadata_cannot_be_changed_to_claim_a_different_definition():
    p = project('f(x)=FractionalDerivative(1,(x,0),1/2,"caputo")', POSITIVE)
    data = json.loads(dumps(p))
    data["objects"][0]["expression"]["value"] = "builtin:rl-derivative"
    with pytest.raises(ValueError, match="identity"):
        loads(json.dumps(data))
    data = json.loads(dumps(p))
    data["constructions"][0]["description"] = "Different semantics"
    with pytest.raises(ValueError, match="Modified builtin"):
        loads(json.dumps(data))


def test_all_legacy_example_projects_still_load():
    from pathlib import Path
    for path in (Path(__file__).parents[1] / "examples").glob("*.json"):
        assert loads(path.read_text()).objects


def test_workbench_domain_changes_invalidate_results_without_overwriting_other_context():
    from mathsandbox.ui.workbench import Workbench
    session = Workbench()
    session.apply('root(x)=x^(1/2)\ncomposed(x)=root(x)')
    assert session.project.evaluate("root").status == "unevaluated"
    session.set_domain("root", "PositiveReals")
    equivalent(session.project, "root", lambda x: sp.sqrt(x))
    assert session.project.evaluate("composed").status == "unevaluated"
    session.set_domain("composed", "PositiveReals")
    equivalent(session.project, "composed", lambda x: sp.sqrt(x))
    session.set_domain("root", "Reals")
    assert session.project.names["composed"] not in session.project.representations
    assert session.project.evaluate("composed").status == "unevaluated"


@pytest.mark.parametrize("name,selected", [("tower", "tower"), ("fractional", "integral"), ("iteration", "twice")])
def test_workbench_a2_examples_have_licensed_exact_results_and_numeric_views(name, selected):
    from mathsandbox.ui.workbench import Workbench
    session = Workbench()
    session.choose_example(name)
    result = session.render({**session.view, "mode": "numeric", "coordinate": "2"})
    assert session.view["name"] == selected
    assert result["symbolic_status"] == "exact", result["provenance"]["diagnostic"]
    assert result["point"]["status"] == "numerically-computed"
    assert any(row["y"] is not None for row in result["plot"]["samples"])
    restored = Workbench()
    restored.restore(session.export())
    assert restored.project.objects == session.project.objects
    assert restored.project.transformations == session.project.transformations
    assert restored.view == session.view


def test_fractional_integral_agrees_with_defining_quadrature():
    p = project('f(x)=FractionalIntegral(x^2,(x,0),1/2,"riemann-liouville")', POSITIVE)
    p.evaluate("f")
    with mp.workdps(40):
        x, alpha = mp.mpf(2), mp.mpf("0.5")
        integral = mp.quad(lambda t: (x-t)**(alpha-1)*t**2, [0, x/2, x])/mp.gamma(alpha)
        actual = mp.mpf(point(p, "f", "2", digits=40).value)
        assert abs(actual-integral) < mp.mpf("1e-18")


def test_family_zero_one_and_additive_time_composition():
    p = project("f(x)=x^2")
    p.define('one(x)=Iterate(f,1,x,"positive-power")', POSITIVE)
    p.define('a(x)=Iterate(f,1/3,x,"positive-power")', POSITIVE)
    p.define('b(x)=Iterate(f,2/3,x,"positive-power")', POSITIVE)
    p.define("combined(x)=a(b(x))", POSITIVE)
    equivalent(p, "one", lambda x: x**2)
    equivalent(p, "combined", lambda x: x**2)


def test_real_universe_does_not_silently_license_complex_intermediates():
    p = project("f(x)=I*I")
    assert p.evaluate("f").status == "unevaluated"
    with pytest.raises(ValueError, match="real-only"):
        point(p, "f", "1")


def test_legacy_custom_gamma_does_not_become_a_builtin_in_fractional_output():
    data = json.loads(dumps(Project()))
    data["operators"] = [op for op in data["operators"] if op["id"] != "builtin:gamma"]
    data["operators"].append(asdict(OperatorDefinition("custom:gamma", "gamma", 1, semantics="opaque")))
    p = loads(json.dumps(data))
    p.define('f(x)=FractionalIntegral(x^(1/3),(x,0),1/2,"riemann-liouville")', POSITIVE)
    assert p.evaluate("f").status == "unevaluated"
    assert p.registry.named("gamma").id == "custom:gamma"


def test_numeric_iteration_expression_has_a_magnitude_guard():
    p = project("f(x)=exp(x)")
    p.define('g(x)=Iterate(f,4,x,"integer")')
    assert p.evaluate("g").status == "exact"
    with pytest.raises(OverflowError, match="budget"):
        point(p, "g", "2")
