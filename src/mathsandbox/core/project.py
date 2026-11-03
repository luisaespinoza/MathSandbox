import sympy
from .ir import Context, Expr, MathObject, Provenance, Representation, identity
from .parser import Parser
from ..operators.registry import OperatorRegistry
from ..adapters.sympy_backend import evaluate


def calls(expression: Expr) -> set[str]:
    result = {expression.value} if expression.kind == "call" else set()
    for arg in expression.args:
        result.update(calls(arg))
    return result


class Project:
    def __init__(self) -> None:
        self.registry = OperatorRegistry()
        self.objects: dict[str, MathObject] = {}
        self.representations: dict[str, Representation] = {}
        self.history: list[MathObject] = []
        self.transformations: list[Representation] = []

    @property
    def names(self) -> dict[str, str]:
        return {obj.name: obj.id for obj in self.objects.values()}

    def closure(self, object_id: str, objects=None) -> set[str]:
        objects = self.objects if objects is None else objects
        visited: set[str] = set()
        active: set[str] = set()
        def visit(current):
            if current in active:
                raise ValueError("Circular dependency")
            if current in visited:
                return
            if current not in objects:
                raise ValueError("Missing dependency")
            active.add(current)
            for dep in objects[current].dependencies:
                visit(dep)
            active.remove(current)
            visited.add(current)
        visit(object_id)
        return visited

    def define(self, text: str, context: Context | None = None) -> MathObject:
        name_match = text.split("(", 1)[0].strip()
        names = self.names
        if any(d.name == name_match for d in self.registry.definitions.values()) or name_match in ("Integral", "diff"):
            raise ValueError("Reserved operator name")
        object_id = names.get(name_match, identity())
        names[name_match] = object_id
        name, parameters, expression = Parser(self.registry, names).definition(text)
        old = self.objects.get(object_id)
        obj = MathObject(object_id, name, parameters, expression, text,
                         context if context is not None else (old.context if old else Context()),
                         tuple(sorted(calls(expression))), old.revision + 1 if old else 1)
        proposed = {**self.objects, object_id: obj}
        for item in proposed.values():
            self.closure(item.id, proposed)
            self.validate_expression(item.expression, proposed)
        if old:
            self.history.append(old)
        self.objects[object_id] = obj
        for cached in list(self.representations):
            if object_id in self.closure(cached):
                del self.representations[cached]
        return obj

    def validate_expression(self, node: Expr, objects=None) -> None:
        objects = self.objects if objects is None else objects
        arities = {"integer": 0, "symbol": 0, "integral": 4, "derivative": 2}
        if node.kind == "operator":
            arity = self.registry.definitions[node.value].arity
        elif node.kind == "call":
            arity = len(objects[node.value].parameters)
        elif node.kind in arities:
            arity = arities[node.kind]
        else:
            raise ValueError("Unknown expression kind")
        if len(node.args) != arity:
            raise ValueError("Expression arity mismatch")
        if node.kind == "integer":
            int(node.value)
        if node.kind in ("integral", "derivative") and node.args[1].kind != "symbol":
            raise ValueError("Invalid bound variable")
        for arg in node.args:
            self.validate_expression(arg, objects)

    def evaluate(self, name: str, *, keep_unevaluated: bool = False, timeout: float = 10.0) -> Representation:
        obj = self.objects[self.names[name]]
        if obj.id in self.representations and not keep_unevaluated:
            return self.representations[obj.id]
        expression, status = (obj.expression, "unevaluated") if keep_unevaluated else evaluate(obj.expression, self.objects, self.registry, obj.context, timeout)
        provenance = Provenance(obj.id, obj.revision,
            tuple(sorted((i, self.objects[i].revision) for i in self.closure(obj.id))),
            "keep-unevaluated" if keep_unevaluated else "symbolic-evaluation", "SymPy", sympy.__version__, obj.context)
        result = Representation(expression, status, provenance)
        self.transformations.append(result)
        if not keep_unevaluated and status == "exact":
            self.representations[obj.id] = result
        return result

    def to_sympy(self, name: str):
        """Inspection helper; the authoritative result remains backend-independent IR."""
        from ..adapters.sympy_backend import Translator, compatible, IncompatibleSemantics
        obj = self.objects[self.names[name]]
        if not compatible(obj.context):
            raise IncompatibleSemantics("Context is unsupported")
        result = self.evaluate(name)
        if result.status != "exact":
            raise IncompatibleSemantics("No exact licensed representation; inspect evaluate().expression instead")
        return Translator(self.objects, self.registry, obj.context).translate(result.expression)
