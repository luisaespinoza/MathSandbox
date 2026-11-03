"""UI-independent workbench session; definitions remain authoritative."""
from copy import deepcopy
from dataclasses import asdict
import json
import sympy as sp
from ..core.project import Project
from ..storage.json_project import dumps, loads
from ..visualization.sampling import PlotSettings, compute

DEMO = "f(x) = x^3\ng(x) = sin(x)\nh(x) = Integral(f(g(t)), (t, 0, x))\np(x) = diff(h(x), x)"


class Workbench:
    def __init__(self):
        self.project = Project()
        self.view = {"name": "p", "mode": "exact", "coordinate": "1", **asdict(PlotSettings())}
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

    def state(self):
        return {"objects": [{"id": obj.id, "name": obj.name, "definition": obj.original_definition,
                             "revision": obj.revision, "context": asdict(obj.context),
                             "dependencies": [self.project.objects[d].name for d in obj.dependencies]}
                            for obj in self.project.objects.values()], "view": self.view}

    def render(self, view):
        if view.get("mode") not in ("exact", "numeric", "unevaluated"):
            raise ValueError("Unknown evaluation mode")
        settings = PlotSettings(**{key: view.get(key, default) for key, default in asdict(PlotSettings()).items()})
        settings.validate()
        name = view["name"]
        if name not in self.project.names:
            raise ValueError("Select a defined function")
        mode = view["mode"]
        result = self.project.evaluate(name, keep_unevaluated=(mode == "unevaluated"))
        obj = self.project.objects[self.project.names[name]]
        self.view = {"name": name, "mode": mode, "coordinate": str(view.get("coordinate", "")), **asdict(settings)}
        output = {"definition": obj.original_definition, "symbolic_status": result.status,
                  "expression": obj.original_definition.split("=", 1)[1].strip(),
                  "provenance": asdict(result.provenance), "context": asdict(obj.context),
                  "plot": None, "point": None, "notice": ""}
        if result.status == "exact":
            expression = self.project.to_sympy(name)
            # Display names only; unique identities remain intact in core IR.
            display = expression.xreplace({s: sp.Symbol(s.name) for s in expression.free_symbols})
            output["expression"] = str(display)
        if mode == "unevaluated":
            output["notice"] = "Original definition retained. Plotting and numerical evaluation are off in this mode."
            return output
        try:
            output.update(compute(self.project, name, settings, self.view["coordinate"] if mode == "numeric" else ""))
        except ValueError as error:
            output["notice"] = str(error)
        return output

    def export(self):
        data = json.loads(dumps(self.project))
        data["workbench"] = {"schema_version": 1, "view": self.view}
        return json.dumps(data, indent=2) + "\n"

    def restore(self, text):
        project = loads(text)
        data = json.loads(text)
        metadata = data.get("workbench", {})
        if not isinstance(metadata, dict) or not isinstance(metadata.get("view", {}), dict):
            raise ValueError("Malformed workbench metadata")
        view = metadata.get("view", {})
        if metadata and metadata.get("schema_version") != 1:
            raise ValueError("Unsupported workbench schema version")
        if not project.names:
            raise ValueError("Project contains no functions")
        if view.get("mode", "exact") not in ("exact", "numeric", "unevaluated"):
            raise ValueError("Unknown evaluation mode")
        PlotSettings(**{k: view.get(k, v) for k, v in asdict(PlotSettings()).items()}).validate()
        self.project = project
        valid_name = view.get("name") in project.names
        self.view = {"name": view.get("name") if valid_name else next(iter(project.names), ""),
                     "mode": view.get("mode", "exact"), "coordinate": str(view.get("coordinate", "1")),
                     **{k: view.get(k, v) for k, v in asdict(PlotSettings()).items()}}
        return self.state()
