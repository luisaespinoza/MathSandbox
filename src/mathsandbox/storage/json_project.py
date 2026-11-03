"""Versioned JSON, with no executable expression strings or pickle payloads."""
from dataclasses import asdict
import json
from pathlib import Path
from ..core.ir import Context, Expr, MathObject, Provenance, Representation
from ..core.project import Project, calls
from ..operators.registry import OperatorDefinition

SCHEMA_VERSION = 1


def expression(data: dict) -> Expr:
    if set(data) != {"kind", "value", "args"} or not isinstance(data["value"], str):
        raise ValueError("Invalid expression record")
    return Expr(data["kind"], data["value"], tuple(expression(a) for a in data["args"]))


def context(data: dict) -> Context:
    return Context(**{**data, **{k: tuple(data[k]) for k in ("assumptions", "branches", "axioms")}})


def math_object(data: dict) -> MathObject:
    return MathObject(**{**data, "parameters": tuple(expression(p) for p in data["parameters"]),
                         "expression": expression(data["expression"]), "context": context(data["context"]),
                         "dependencies": tuple(data["dependencies"])})


def representation(data: dict) -> Representation:
    provenance = data["provenance"]
    if data["status"] not in ("exact", "unevaluated"):
        raise ValueError("Unknown representation status")
    return Representation(expression(data["expression"]), data["status"], Provenance(**{
        **provenance, "context": context(provenance["context"]),
        "dependency_revisions": tuple(tuple(pair) for pair in provenance["dependency_revisions"])}))


def dumps(project: Project) -> str:
    data = {"schema_version": SCHEMA_VERSION,
            "operators": [asdict(d) for d in project.registry.definitions.values()],
            "objects": [asdict(o) for o in project.objects.values()],
            "history": [asdict(o) for o in project.history],
            "transformations": [asdict(r) for r in project.transformations],
            "representations": {key: asdict(value) for key, value in project.representations.items()}}
    return json.dumps(data, indent=2) + "\n"


def _loads(text: str) -> Project:
    data = json.loads(text)
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported project schema version")
    project = Project()
    builtin = dict(project.registry.definitions)
    project.registry.definitions.clear()
    for item in data["operators"]:
        definition = OperatorDefinition(**item)
        if definition.id.startswith("builtin:") and builtin.get(definition.id) != definition:
            raise ValueError("Modified builtin semantics")
        project.registry.register(definition)
    custom_factorial = any(d.name == "factorial" and d.id != "builtin:factorial"
                           for d in project.registry.definitions.values())
    if "builtin:factorial" not in project.registry.definitions and not custom_factorial:
        project.registry.register(builtin["builtin:factorial"])
    if any(project.registry.definitions.get(k) != v for k, v in builtin.items()
           if not (k == "builtin:factorial" and custom_factorial)):
        raise ValueError("Missing builtin operators")
    for item in data["objects"]:
        obj = math_object(item)
        if obj.id in project.objects or obj.name in project.names:
            raise ValueError("Duplicate object identity or name")
        project.objects[obj.id] = obj
    for obj in project.objects.values():
        if set(obj.dependencies) != calls(obj.expression):
            raise ValueError("Dependency metadata mismatch")
        project.closure(obj.id)
        project.validate_expression(obj.expression)
        if any(p.kind != "symbol" for p in obj.parameters) or len(set(obj.parameters)) != len(obj.parameters):
            raise ValueError("Invalid parameter bindings")
        def check_scope(node, scope):
            if node.kind == "symbol" and node.value not in scope:
                raise ValueError("Unbound symbol in project")
            if node.kind == "integral":
                body, variable, lower, upper = node.args
                check_scope(body, scope | {variable.value})
                check_scope(lower, scope)
                check_scope(upper, scope)
            else:
                for arg in node.args:
                    check_scope(arg, scope)
        check_scope(obj.expression, {p.value for p in obj.parameters})
    project.history = [math_object(o) for o in data["history"]]
    project.transformations = [representation(r) for r in data["transformations"]]
    # Retain saved results as historical records; recompute current caches on demand.
    # JSON is a project record, never an independently checked mathematical certificate.
    for key, item in data["representations"].items():
        result = representation(item)
        if key not in project.objects:
            raise ValueError("Representation has missing source")
        if result not in project.transformations:
            project.transformations.append(result)
    return project


def save(project: Project, path: str | Path) -> None:
    Path(path).write_text(dumps(project), encoding="utf-8")


def load(path: str | Path) -> Project:
    return loads(Path(path).read_text(encoding="utf-8"))


def loads(text: str) -> Project:
    try:
        return _loads(text)
    except (AttributeError, KeyError, TypeError, StopIteration) as error:
        raise ValueError("Malformed project JSON") from error
