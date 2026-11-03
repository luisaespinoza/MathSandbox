import json
import sympy as sp
import pytest
from mathsandbox import Context, OperatorDefinition, Project, load, save


def demo():
    project = Project()
    for text in ("f(x)=x^3", "g(x)=sin(x)", "h(x)=Integral(f(g(t)), (t,0,x))", "p(x)=diff(h(x),x)"):
        project.define(text)
    return project


def equivalent(actual, expected):
    x = sp.Symbol("x", real=True)
    actual = actual.xreplace({s: x for s in actual.free_symbols})
    assert sp.simplify(actual - expected(x)) == 0


def test_composition_exact_integral_and_derivative():
    project = demo()
    equivalent(project.to_sympy("h"), lambda x: sp.Rational(2, 3)-sp.cos(x)+sp.cos(x)**3/3)
    equivalent(project.to_sympy("p"), lambda x: sp.sin(x)**3)
    result = project.evaluate("h")
    assert result.status == "exact"
    assert result.provenance.backend_version == sp.__version__
    assert len(result.provenance.dependency_revisions) == 3
    assert project.objects[project.names["h"]].expression.kind == "integral"


def test_reactive_invalidation_and_history():
    project = demo()
    project.evaluate("p")
    project.evaluate("f")
    before = project.objects[project.names["g"]]
    project.define("g(x)=sin(2*x)")
    assert project.names["p"] not in project.representations
    assert project.names["f"] in project.representations
    equivalent(project.to_sympy("p"), lambda x: sp.sin(2*x)**3)
    assert project.history == [before]
    assert project.objects[before.id].revision == 2


def test_capture_avoidance_and_simultaneous_arguments():
    project = Project()
    project.define("f(x)=Integral(x+t,(t,0,1))")
    project.define("g(t)=f(t)")
    equivalent(project.to_sympy("g"), lambda x: x+sp.Rational(1,2))
    project.define("swap(x,y)=x-y")
    project.define("use(x,y)=swap(y,x)")
    value = project.to_sympy("use")
    symbols = {s.name: s for s in value.free_symbols}
    assert sp.expand(value - (symbols["y"]-symbols["x"])) == 0


def test_bound_scope_does_not_capture_endpoint():
    project = Project()
    project.define("f(t)=Integral(t,(t,0,t))")
    equivalent(project.to_sympy("f"), lambda x: x*x/2)


def test_cycle_and_arity_edits_are_atomic():
    project = Project()
    project.define("f(x)=x")
    project.define("g(x)=f(x)")
    with pytest.raises(ValueError, match="Circular"):
        project.define("f(x)=g(x)")
    with pytest.raises(ValueError, match="arity"):
        project.define("f(x,y)=x+y")
    equivalent(project.to_sympy("f"), lambda x: x)


@pytest.mark.parametrize("text", ["f(x)=__import__('os')", "f(x)=x.real", "f(x)=y", "f(x)=1.2", "f(x,x)=x"])
def test_parser_rejects_unsupported_or_unsafe_input(text):
    with pytest.raises((ValueError, SyntaxError)):
        Project().define(text)


def test_custom_operator_is_never_multiplication(tmp_path):
    project = Project()
    project.registry.register(OperatorDefinition("custom:star", "star", 2, semantics="right-projection", notation="⋆"))
    project.define("f(x)=star(x,0)")
    result = project.evaluate("f")
    assert result.status == "unevaluated"
    assert result.expression.value == "custom:star"
    path = tmp_path / "project.json"
    save(project, path)
    restored = load(path)
    assert restored.registry.definitions == project.registry.definitions
    assert restored.evaluate("f").status == "unevaluated"


@pytest.mark.parametrize("context", [Context(universe_id="custom"), Context(domain="Complexes"), Context(assumptions=("x>0",)), Context(branches=("multivalued",)), Context(axioms=("inconsistent",))])
def test_unlicensed_context_preserved(context, tmp_path):
    project = Project()
    project.define("f(x)=log(x)", context)
    result = project.evaluate("f")
    assert result.status == "unevaluated"
    assert result.provenance.context == context
    path = tmp_path / "p.json"
    save(project, path)
    restored = load(path)
    assert restored.objects == project.objects
    assert restored.evaluate("f").provenance.context == context


def test_context_cannot_leak_across_calls():
    project = Project()
    project.define("f(x)=x", Context(universe_id="custom"))
    project.define("g(x)=f(x)")
    assert project.evaluate("g").status == "unevaluated"


def test_roundtrip_and_schema_rejection(tmp_path):
    project = demo()
    project.evaluate("h")
    project.define("g(x)=sin(2*x)")
    project.evaluate("p")
    path = tmp_path / "p.json"
    save(project, path)
    restored = load(path)
    assert restored.objects == project.objects
    assert restored.history == project.history
    assert restored.transformations == project.transformations
    equivalent(restored.to_sympy("p"), lambda x: sp.sin(2*x)**3)
    data = json.loads(path.read_text())
    data["schema_version"] = 99
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="schema"):
        load(path)


def test_timeout_and_keep_unevaluated():
    project = demo()
    assert project.evaluate("h", timeout=0).status == "unevaluated"
    project = demo()
    assert project.evaluate("h", keep_unevaluated=True).status == "unevaluated"
    assert project.evaluate("h").status == "exact"


def test_tampered_graph_rejected(tmp_path):
    project = demo()
    path = tmp_path / "p.json"
    save(project, path)
    data = json.loads(path.read_text())
    data["objects"][2]["dependencies"] = []
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Dependency"):
        load(path)


@pytest.mark.parametrize("definition", ["f(x)=x/x", "f(x)=x^(1/2)", "f(x)=log(x)", "f(x)=0^(-1)"])
def test_domain_and_branch_obligations_not_simplified_away(definition):
    project = Project()
    obj = project.define(definition)
    result = project.evaluate("f")
    assert result.status == "unevaluated"
    assert result.expression == obj.expression


def test_composition_with_derivative_body():
    project = Project()
    project.define("f(x)=diff(x^3,x)")
    project.define("g(t)=f(t+1)")
    equivalent(project.to_sympy("g"), lambda x: 3*(x+1)**2)


def test_saved_binder_identity_tampering_rejected(tmp_path):
    project = demo()
    path = tmp_path / "p.json"
    save(project, path)
    data = json.loads(path.read_text())
    data["objects"][0]["expression"]["args"][0]["value"] = "unbound"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Unbound"):
        load(path)


def test_inspection_helper_cannot_bypass_semantic_gate():
    project = Project()
    project.define("f(x)=x/x")
    with pytest.raises(ValueError, match="licensed"):
        project.to_sympy("f")


def test_recompute_updated_integral():
    project = demo()
    project.evaluate("h")
    project.define("g(x)=sin(2*x)")
    equivalent(project.to_sympy("h"), lambda x: sp.Rational(1,3)-sp.cos(2*x)/2+sp.cos(2*x)**3/6)
