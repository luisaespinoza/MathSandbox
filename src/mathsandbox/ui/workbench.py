"""UI-independent workbench session; definitions remain authoritative."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
import platform
import sympy as sp
from ..core.project import Project
from ..core.ir import Context
from ..storage.json_project import dumps, loads
from ..visualization.sampling import PlotSettings
from ..visualization.geometry import GeometrySettings, compute_geometry
from ..adapters.complex_numeric import COMPLEX_CONTEXT
from ..adapters.padic import RATIONAL_CONTEXT

DEMO = "f(x) = x^3\ng(x) = sin(x)\nh(x) = Integral(f(g(t)), (t, 0, x))\np(x) = diff(h(x), x)"


class Workbench:
    def __init__(self):
        self.project = Project()
        self.view_records = []
        self.view = {"name": "p", "mode": "exact", "coordinate": "1", **asdict(PlotSettings()), **asdict(GeometrySettings())}
        self.apply(DEMO)

    def apply(self, text):
        # A parse error on any line must leave the entire session intact.
        if not isinstance(text, str):
            raise ValueError("Definitions must be text")
        proposed = deepcopy(self.project)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            raise ValueError("Enter at least one definition")
        for line in lines:
            name = line.split("(", 1)[0].strip()
            old = proposed.objects.get(proposed.names.get(name))
            if not old or old.original_definition != line:
                proposed.define(line)
        self.project = proposed
        return self.state()

    def set_domain(self, name, domain):
        if domain not in ("Reals", "PositiveReals", "Complexes", "Rationals") or name not in self.project.names:
            raise ValueError("Select an existing function and a supported input domain")
        obj = self.project.objects[self.project.names[name]]
        if obj.context.domain != domain:
            context = replace(obj.context, domain=domain)
            if obj.context.universe_id in ("standard-real", "standard-complex", "standard-rational"):
                universe, codomain = {"Complexes": ("standard-complex", "Complexes"),
                                      "Rationals": ("standard-rational", "Rationals")}.get(domain, ("standard-real", "Reals"))
                context = replace(context, universe_id=universe, codomain=codomain)
            self.project.define(obj.original_definition, context)
        return self.state()

    def choose_example(self, name):
        if name == "composition":
            self.__init__()
            return self.state()
        if name in ("complex", "padic"):
            self.project = Project()
            self.view_records = []
            definitions = ["f(z) = 1/(z^2+1)", "logarithm(z) = log(z)", "root(z) = z^(1/2)"] if name == "complex" else ["f(x) = x"]
            for definition in definitions:
                self.project.define(definition, COMPLEX_CONTEXT if name == "complex" else RATIONAL_CONTEXT)
            self.view = {"name": "f", "mode": "numeric" if name == "complex" else "exact",
                         "coordinate": "1" if name == "complex" else "125",
                         **asdict(PlotSettings(lower="-2", upper="2")),
                         **asdict(GeometrySettings(geometry="complex-compare" if name == "complex" else "padic-tree"))}
            return self.state()
        definitions = {
            "factorial": ["f(x) = factorial(x)"],
            "tower": ["tower(x) = Tower(x, (k, 1, 3), 1)",
                      "heterogeneous(x) = Tower(k+1, (k, 1, 3), 1)"],
            "fractional": ['integral(x) = FractionalIntegral(x^2, (x, 0), 1/2, "riemann-liouville")',
                           'rl(x) = FractionalDerivative(1, (x, 0), 1/2, "riemann-liouville")',
                           'caputo(x) = FractionalDerivative(1, (x, 0), 1/2, "caputo")'],
            "iteration": ["f(x) = x^2", 'half(x) = Iterate(f, 1/2, x, "positive-power")',
                          "twice(x) = half(half(x))"],
        }
        if name not in definitions:
            raise ValueError("Unknown example")
        self.project = Project()
        self.view_records = []
        context = Context() if name == "factorial" else Context(domain="PositiveReals")
        for definition in definitions[name]:
            self.project.define(definition, context)
        self.view = {"name": {"factorial": "f", "tower": "tower", "fractional": "integral", "iteration": "twice"}[name],
                     "mode": "exact", "coordinate": "1", **asdict(PlotSettings(lower="0.25", upper="3")), **asdict(GeometrySettings())}
        if name == "factorial":
            self.view.update(lower="1", upper="30", y_scale="factorial", gamma_factorial=True)
        if name == "tower":
            self.view.update(upper="2")
        return self.state()

    def state(self):
        return {"objects": [{"id": obj.id, "name": obj.name, "definition": obj.original_definition,
                             "revision": obj.revision, "context": asdict(obj.context),
                             "dependencies": [self.project.objects[d].name for d in obj.dependencies]}
                            for obj in self.project.objects.values()], "view": self.view}

    def render(self, view):
        if view.get("mode") not in ("exact", "numeric", "unevaluated"):
            raise ValueError("Unknown evaluation mode")
        settings = PlotSettings(**{key: view.get(key, default) for key, default in asdict(PlotSettings()).items()})
        geometry = GeometrySettings(**{key: view.get(key, default) for key, default in asdict(GeometrySettings()).items()})
        geometry.validate(settings)
        name = view["name"]
        if name not in self.project.names:
            raise ValueError("Select a defined function")
        mode = view["mode"]
        result = self.project.evaluate(name, keep_unevaluated=(mode == "unevaluated"))
        obj = self.project.objects[self.project.names[name]]
        self.view = {"name": name, "mode": mode, "coordinate": str(view.get("coordinate", "")), **asdict(settings), **asdict(geometry)}
        output = {"definition": obj.original_definition, "symbolic_status": result.status,
                  "expression": obj.original_definition.split("=", 1)[1].strip(),
                  "provenance": asdict(result.provenance), "context": asdict(obj.context),
                  "plot": None, "point": None, "notice": result.provenance.diagnostic if result.status == "unevaluated" else ""}
        if result.status == "exact":
            expression = self.project.to_sympy(name)
            # Display names only; unique identities remain intact in core IR.
            display = expression.xreplace({s: sp.Symbol(s.name) for s in expression.free_symbols})
            output["expression"] = str(display)
        if mode == "unevaluated":
            output["notice"] = "Original definition retained. Plotting and numerical evaluation are off in this mode."
            return output
        try:
            coordinate = self.view["coordinate"] if mode == "numeric" or geometry.geometry.startswith("padic") else ""
            output.update(compute_geometry(self.project, name, settings, geometry, coordinate))
            if geometry.geometry != "real" and output["plot"]:
                output["notice"] = "Symbolic definition retained. " + ("This view uses exact rational arithmetic and finite residue precision." if geometry.geometry.startswith("padic") else "Complex samples use the selected principal branch; no analytic continuation is inferred.")
        except ValueError as error:
            output["notice"] = "\n".join(filter(None, (output["notice"], str(error))))
        if output["plot"] is not None:
            plot = output["plot"]
            keys = ("kind", "status", "backend", "backend_version", "context", "source_id", "source_revision",
                    "dependency_revisions", "settings", "conventions", "error_estimate", "warnings",
                    "input", "rational", "prime", "precision", "valuation", "norm", "unit_part",
                    "unit_residue", "modulus", "digits", "absolute_precision")
            record = {key: plot[key] for key in keys if key in plot}
            record.update(kind=plot.get("kind", "real"), adapter="mathsandbox-geometry-v1", python_version=platform.python_version(),
                          name=name, mode=mode, requested_coordinate=self.view["coordinate"], point=output["point"])
            record = json.loads(json.dumps(record, allow_nan=False))  # Detached, stable JSON representation.
            if not self.view_records or self.view_records[-1] != record:
                self.view_records.append(deepcopy(record))
        return output

    def export(self):
        data = json.loads(dumps(self.project))
        data["workbench"] = {"schema_version": 2, "view": self.view, "view_records": self.view_records}
        return json.dumps(data, indent=2) + "\n"

    def restore(self, text):
        project = loads(text)
        data = json.loads(text)
        metadata = data.get("workbench", {})
        if not isinstance(metadata, dict) or not isinstance(metadata.get("view", {}), dict):
            raise ValueError("Malformed workbench metadata")
        view = metadata.get("view", {})
        records = metadata.get("view_records", [])
        if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
            raise ValueError("Malformed view provenance records")
        if metadata and metadata.get("schema_version") not in (1, 2):
            raise ValueError("Unsupported workbench schema version")
        if not project.names:
            raise ValueError("Project contains no functions")
        if view.get("mode", "exact") not in ("exact", "numeric", "unevaluated"):
            raise ValueError("Unknown evaluation mode")
        restored_settings = PlotSettings(**{k: view.get(k, v) for k, v in asdict(PlotSettings()).items()})
        restored_geometry = GeometrySettings(**{k: view.get(k, v) for k, v in asdict(GeometrySettings()).items()})
        restored_geometry.validate(restored_settings)
        self.project = project
        self.view_records = deepcopy(records)
        valid_name = view.get("name") in project.names
        self.view = {"name": view.get("name") if valid_name else next(iter(project.names), ""),
                     "mode": view.get("mode", "exact"), "coordinate": str(view.get("coordinate", "1")),
                     **asdict(restored_settings), **asdict(restored_geometry)}
        return self.state()
