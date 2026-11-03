from dataclasses import asdict
import http.client
import json
import math
import threading
import mpmath as mp
import pytest
from mathsandbox import Context, OperatorDefinition, Project
from mathsandbox.adapters.numeric import NumericEvaluator, point
from mathsandbox.storage.json_project import dumps, loads
from mathsandbox.ui.server import WorkbenchServer
from mathsandbox.ui.workbench import Workbench, DEMO
from mathsandbox.visualization.sampling import PlotSettings, sample, compute
from mathsandbox.visualization.scales import transform


def function(text):
    project = Project()
    project.define(text)
    return project


def test_numeric_precision_and_source_preservation():
    project = function("f(x)=1/3+x")
    before = dumps(project)
    low = point(project, "f", "0", digits=15)
    high = point(project, "f", "0", digits=80)
    assert len(high.value) > len(low.value)+50
    assert high.value.startswith("0.333333333333333333333333333333333333")
    assert high.status == "numerically-computed" and high.error_estimate == "not certified"
    assert dumps(project) == before


def test_numeric_does_not_cancel_excluded_points():
    project = function("f(x)=x/x")
    assert point(project, "f", "2").value == "1.0"
    with pytest.raises((ValueError, ZeroDivisionError)):
        point(project, "f", "0")
    plot = sample(project, "f", PlotSettings(lower="-1", upper="1"))
    assert any(row["y"] is None for row in plot["samples"])
    assert plot["warnings"]


def test_domain_boundaries_and_pole_are_not_connected():
    project = function("f(x)=1/x")
    rows = sample(project, "f", PlotSettings(lower="-1", upper="1"))["samples"]
    negative = [i for i, row in enumerate(rows) if row["y"] is not None and float(row["raw_x"]) < 0]
    positive = [i for i, row in enumerate(rows) if row["y"] is not None and float(row["raw_x"]) > 0]
    assert negative and positive
    assert any(row["y"] is None for row in rows[max(negative):min(positive)+1])
    log = sample(function("f(x)=log(x)"), "f", PlotSettings(lower="-2", upper="2"))
    assert all(row["y"] is None for row in log["samples"] if float(row["raw_x"]) <= 0)


def test_adaptive_sampling_refines_curvature():
    linear = sample(function("f(x)=x"), "f", PlotSettings(lower="0", upper="10"))
    curved = sample(function("f(x)=exp(5*x)"), "f", PlotSettings(lower="0", upper="10"))
    assert len(curved["samples"]) > len(linear["samples"])
    assert any(row["y"] is not None for row in curved["samples"])
    assert len(curved["samples"]) < 2000


def test_scales_are_explicit_and_view_only():
    with mp.workdps(40):
        assert abs(transform(mp.mpf(1000), "log")-3) < mp.mpf("1e-30")
        assert transform(mp.mpf(-9), "symlog") == -1
        for n in (1, 2, 10, 30):
            assert abs(transform(mp.factorial(n), "factorial")-n) < mp.mpf("1e-10")
        with pytest.raises(ValueError):
            transform(mp.mpf(0), "log")
        with pytest.raises(ValueError):
            transform(mp.mpf("0.5"), "factorial")
    project = function("f(x)=exp(x)")
    original = dumps(project)
    settings = PlotSettings(lower="1", upper="3", x_scale="log", y_scale="log")
    plot = sample(project, "f", settings)
    assert plot["settings"]["x_scale"] == "log"
    assert dumps(project) == original
    assert float(plot["samples"][0]["raw_x"]) == 1
    assert plot["samples"][0]["x"] == 0


def test_factorial_gamma_extension_requires_selection():
    project = function("f(x)=factorial(x)")
    assert point(project, "f", "5").value == "120.0"
    with pytest.raises(ValueError, match="Gamma"):
        point(project, "f", "1.5")
    result = point(project, "f", "1.5", gamma_factorial=True)
    assert abs(float(result.value) - float(mp.gamma(mp.mpf("2.5")))) < 1e-14
    for extension in (False, True):
        with pytest.raises(ValueError):
            point(project, "f", "-1", gamma_factorial=extension)
    plot = sample(project, "f", PlotSettings(lower="1", upper="8", y_scale="factorial", gamma_factorial=True))
    for row in plot["samples"]:
        assert row["y"] == pytest.approx(float(row["raw_x"]), abs=1e-10)
    assert project.evaluate("f").status == "unevaluated"
    assert function("f(x)=factorial(5)").evaluate("f").status == "exact"


def test_custom_context_and_operator_refused_numerically():
    project = Project()
    project.define("f(x)=x", Context(branches=("multivalued",)))
    with pytest.raises(ValueError, match="context"):
        NumericEvaluator(project, "f")
    project = Project()
    project.registry.register(OperatorDefinition("custom:star", "star", 2))
    project.define("f(x)=star(x,0)")
    with pytest.raises(ValueError, match="licensed"):
        point(project, "f", "1")


def test_atomic_multiline_edit_and_invalid_import():
    session = Workbench()
    original = dumps(session.project)
    with pytest.raises(ValueError):
        session.apply("g(x)=sin(2*x)\nbad(x)=unbound")
    assert dumps(session.project) == original
    with pytest.raises(ValueError):
        session.restore("[]")
    assert dumps(session.project) == original
    data = json.loads(session.export())
    data["workbench"]["view"]["lower"] = "not a number"
    with pytest.raises(ValueError):
        session.restore(json.dumps(data))
    assert dumps(session.project) == original


def test_saved_views_and_core_compatibility():
    session = Workbench()
    session.view.update(lower="1", upper="4", y_scale="log", digits=70, gamma_factorial=True)
    saved = session.export()
    restored = Workbench()
    restored.restore(saved)
    assert restored.view == session.view
    assert restored.project.objects == session.project.objects
    core_only = loads(saved)
    assert core_only.objects == session.project.objects
    # Pre-A1 JSON remains loadable despite the additive builtin operator.
    data = json.loads(dumps(core_only))
    data["operators"] = [d for d in data["operators"] if d["id"] != "builtin:factorial"]
    assert loads(json.dumps(data)).objects == core_only.objects


def test_workbench_recomputes_composition_and_provenance():
    session = Workbench()
    view = {**session.view, "mode": "numeric", "coordinate": "1", "lower": "0", "upper": "2"}
    before = session.render(view)
    assert before["symbolic_status"] == "exact"
    assert float(before["point"]["value"]) == pytest.approx(math.sin(1)**3)
    session.apply(DEMO.replace("g(x) = sin(x)", "g(x) = sin(2*x)"))
    after = session.render(view)
    assert float(after["point"]["value"]) == pytest.approx(math.sin(2)**3)
    assert after["plot"]["dependency_revisions"] != before["plot"]["dependency_revisions"]
    source = session.project.objects[session.project.names["p"]]
    assert after["plot"]["context"] == asdict(source.context)
    kept = session.render({**view, "mode": "unevaluated"})
    assert kept["symbolic_status"] == "unevaluated" and kept["plot"] is None
    assert kept["expression"] == "diff(h(x), x)"


def test_worker_timeout_and_invalid_bounds():
    project = function("f(x)=x")
    with pytest.raises(ValueError, match="timed out"):
        compute(project, "f", PlotSettings(), timeout=0)
    for settings in (PlotSettings(lower="nan"), PlotSettings(lower="2", upper="1"),
                     PlotSettings(digits=5), PlotSettings(x_scale="log", lower="-1")):
        with pytest.raises(ValueError):
            settings.validate()


def test_http_launch_assets_edit_and_roundtrip():
    pytest.importorskip("plotly")
    with WorkbenchServer(("127.0.0.1", 0)) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        client = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=40)
        def request(method, path, data=None, token=True):
            headers = {"X-MathSandbox-Token": server.token} if token else {}
            client.request(method, path, json.dumps(data) if data is not None else None, headers)
            response = client.getresponse()
            return response.status, response.read().decode()
        try:
            status, html = request("GET", "/")
            assert status == 200 and "Apply definitions" in html and "__TOKEN__" not in html
            status, js = request("GET", "/plotly.js")
            assert status == 200 and "plotly" in js.lower()
            assert request("POST", "/api/define", {"definitions": "g(x)=sin(2*x)"}, token=False)[0] == 403
            assert request("POST", "/api/define", {"definitions": "g(x)=sin(2*x)"})[0] == 200
            status, text = request("POST", "/api/render", {**server.workbench.view, "mode": "numeric"})
            assert status == 200
            result = json.loads(text)
            assert result["plot"]["samples"]
            assert float(result["point"]["value"]) == pytest.approx(math.sin(2)**3)
            status, saved = request("GET", "/api/export")
            assert status == 200 and json.loads(saved)["workbench"]["schema_version"] == 1
            assert request("POST", "/api/import", {"project": saved})[0] == 200
            assert request("POST", "/api/import", {"project": "not JSON"})[0] == 400
            assert request("POST", "/api/demo", {"example": "factorial"})[0] == 200
            status, text = request("POST", "/api/render", server.workbench.view)
            assert status == 200 and any(r["y"] is not None for r in json.loads(text)["plot"]["samples"])
        finally:
            client.close()
            server.shutdown()
            thread.join()


def test_legacy_custom_factorial_identity_is_preserved():
    project = function("f(x)=x")
    data = json.loads(dumps(project))
    data["operators"] = [d for d in data["operators"] if d["id"] != "builtin:factorial"]
    data["operators"].append(asdict(OperatorDefinition("legacy:factorial", "factorial", 1)))
    restored = loads(json.dumps(data))
    restored.define("g(x)=factorial(x)")
    assert restored.objects[restored.names["g"]].expression.value == "legacy:factorial"
    assert restored.evaluate("g").status == "unevaluated"


def test_saved_extension_choice_is_not_coerced_from_a_string():
    session = Workbench()
    original = dumps(session.project)
    data = json.loads(session.export())
    data["workbench"]["view"]["gamma_factorial"] = "false"
    with pytest.raises(ValueError, match="boolean"):
        session.restore(json.dumps(data))
    assert dumps(session.project) == original


def test_off_grid_pole_has_a_gap_and_budget_is_bounded():
    project = function("f(x)=1/(x-1/7)")
    plot = sample(project, "f", PlotSettings(lower="0", upper="1", max_points=300))
    rows = plot["samples"]
    assert len(rows) < 600
    assert any(row["y"] is None for row in rows)
    assert any(row["y"] is not None for row in rows)
    assert plot["warnings"]


def test_bad_point_does_not_discard_a_valid_plot():
    project = function("f(x)=1/x")
    result = compute(project, "f", PlotSettings(lower="-1", upper="1"), coordinate="0")
    assert result["point"]["status"] == "undefined"
    assert any(row["y"] is not None for row in result["plot"]["samples"])


@pytest.mark.parametrize("metadata", [[], {"view": []}, {"schema_version": 99, "view": {}}])
def test_malformed_workbench_metadata_is_atomic(metadata):
    session = Workbench()
    original = dumps(session.project)
    data = json.loads(session.export())
    data["workbench"] = metadata
    with pytest.raises(ValueError):
        session.restore(json.dumps(data))
    assert dumps(session.project) == original
