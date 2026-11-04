import sympy
from .ir import Context, Expr, MathObject, Provenance, Representation, identity
from .parser import Parser
from ..operators.registry import OperatorRegistry
from ..operators.constructions import ConstructionRegistry
from ..operators.syntax import RESERVED
from ..analysis.registry import TransformationRegistry, TransformationDefinition
from ..analysis.records import AnalyticGerm, AnalysisRecord
from ..adapters.sympy_backend import evaluate


def calls(expression: Expr) -> set[str]:
    result = {expression.value} if expression.kind in ("call", "iterate") else set()
    for arg in expression.args:
        result.update(calls(arg))
    return result


class Project:
    def __init__(self) -> None:
        self.registry = OperatorRegistry()
        self.constructions = ConstructionRegistry()
        self.objects: dict[str, MathObject] = {}
        self.transform_registry = TransformationRegistry()
        self.analytic_germs: dict[str, AnalyticGerm] = {}
        self.analysis_records: list[AnalysisRecord] = []
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
        if any(d.name == name_match for d in self.registry.definitions.values()) or name_match in ("Integral", "diff", *RESERVED):
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
        arities = {"integer": 0, "symbol": 0, "integral": 4, "derivative": 2, "constant": 0, "fold": 5, "fractional": 4, "iterate": 2}
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
        if node.kind == "constant" and node.value not in ("pi", "E", "I"):
            raise ValueError("Unknown mathematical constant")
        if node.kind == "fold":
            if self.registry.definitions[node.value].arity != 2 or node.args[1].kind != "symbol":
                raise ValueError("Invalid fold signature or binder")
            if dict(node.conventions) not in ({"association": "left", "range": "inclusive-integer"},
                                              {"association": "right", "range": "inclusive-integer"}):
                raise ValueError("Invalid fold conventions")
        if node.kind == "fractional":
            if node.args[1].kind != "symbol" or set(dict(node.conventions)) != {"side", "definition", "operation"}:
                raise ValueError("Invalid fractional calculus semantics")
            conventions = dict(node.conventions)
            if conventions["side"] != "left" or conventions["operation"] not in ("integral", "derivative"):
                raise ValueError("Invalid fractional calculus conventions")
            method = conventions["definition"]
            suffix = conventions["operation"]
            expected = {("riemann-liouville", "integral"): "builtin:rl-integral",
                        ("riemann-liouville", "derivative"): "builtin:rl-derivative",
                        ("caputo", "derivative"): "builtin:caputo-derivative"}.get((method, suffix), method+":"+suffix)
            if node.value != expected:
                raise ValueError("Fractional definition identity mismatch")
        if node.kind == "iterate":
            if node.value not in objects or len(objects[node.value].parameters) != 1:
                raise ValueError("Iteration requires a unary function")
            if set(dict(node.conventions)) != {"family"}:
                raise ValueError("Iteration family must be explicit")
        if len(dict(node.conventions)) != len(node.conventions):
            raise ValueError("Duplicate semantic conventions")
        if node.kind not in ("fold", "fractional", "iterate") and node.conventions:
            raise ValueError("Unexpected expression conventions")
        if node.kind in ("integral", "derivative") and node.args[1].kind != "symbol":
            raise ValueError("Invalid bound variable")
        for arg in node.args:
            self.validate_expression(arg, objects)

    def evaluate(self, name: str, *, keep_unevaluated: bool = False, timeout: float = 10.0) -> Representation:
        obj = self.objects[self.names[name]]
        if obj.id in self.representations and not keep_unevaluated:
            return self.representations[obj.id]
        expression, status, rules, diagnostic = (obj.expression, "unevaluated", (), "Kept unevaluated by request") if keep_unevaluated else evaluate(obj.expression, self.objects, self.registry, obj.context, timeout, self.constructions)
        provenance = Provenance(obj.id, obj.revision,
            tuple(sorted((i, self.objects[i].revision) for i in self.closure(obj.id))),
            "keep-unevaluated" if keep_unevaluated else "symbolic-evaluation", "SymPy", sympy.__version__, obj.context, rules, diagnostic)
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
        return Translator(self.objects, self.registry, obj.context, self.constructions).translate(result.expression)

    def register_rewrite(self, name: str, pattern: str, replacement: str):
        import ast
        parameter = Expr("symbol", "x:"+identity())
        parser = Parser(self.registry, {})
        parse = lambda text: parser.expression(ast.parse(text.replace("^", "**"), mode="eval").body, {"x": parameter})
        self.transform_registry.register(TransformationDefinition(name, "rewrite", "User-specified non-destructive rewrite", parameter, parse(pattern), parse(replacement)))
