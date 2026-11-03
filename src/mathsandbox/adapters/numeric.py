"""Pointwise mpmath evaluation. No symbolic cancellation or domain expansion."""
from dataclasses import dataclass
import mpmath as mp
from .sympy_backend import compatible, IncompatibleSemantics
from ..core.ir import Expr
from ..core.project import Project


@dataclass(frozen=True)
class NumericValue:
    value: str
    digits: int
    status: str = "numerically-computed"
    error_estimate: str = "not certified"


class NumericEvaluator:
    def __init__(self, project: Project, name: str, *, gamma_factorial: bool = False):
        self.project = project
        self.obj = project.objects[project.names[name]]
        self.gamma_factorial = gamma_factorial
        if not compatible(self.obj.context):
            raise IncompatibleSemantics("Numeric adapter does not license this context")
        if len(self.obj.parameters) != 1:
            raise ValueError("A1 supports real functions with one parameter")
        result = project.representations.get(self.obj.id)
        self.expression = result.expression if result and result.status == "exact" else self.obj.expression

    def at(self, x):
        return self.node(self.expression, {self.obj.parameters[0].value: mp.mpf(x)})

    def node(self, node: Expr, bindings):
        if node.kind == "integer":
            return mp.mpf(node.value)
        if node.kind == "symbol":
            return bindings[node.value]
        if node.kind == "call":
            obj = self.project.objects[node.value]
            if obj.context != self.obj.context:
                raise IncompatibleSemantics("Function contexts differ")
            values = [self.node(a, bindings) for a in node.args]
            return self.node(obj.expression, {p.value: a for p, a in zip(obj.parameters, values)})
        if node.kind != "operator":
            raise IncompatibleSemantics("Integral/derivative needs an exact representation before numeric evaluation")
        definition = self.project.registry.definitions[node.value]
        name = node.value.removeprefix("builtin:")
        if (node.value != "builtin:" + name or definition.semantics != "standard:" + name
                or definition.universe_id != self.obj.context.universe_id):
            raise IncompatibleSemantics("No licensed numerical operator")
        args = [self.node(a, bindings) for a in node.args]
        if name == "add":
            result = args[0] + args[1]
        elif name == "mul":
            result = args[0] * args[1]
        elif name == "pow":
            if args[0] == 0 and args[1] <= 0:
                raise ValueError("Undefined zero power")
            result = mp.power(*args)
        elif name == "log":
            if args[0] <= 0:
                raise ValueError("Real logarithm requires a positive argument")
            result = mp.log(args[0])
        elif name in ("sin", "cos", "exp"):
            result = getattr(mp, name)(args[0])
        elif name == "factorial":
            x = args[0]
            if x < 0 or (not self.gamma_factorial and x != mp.floor(x)):
                raise ValueError("Factorial requires a nonnegative integer, or the selected Gamma extension")
            result = mp.gamma(x + 1)
        else:
            raise IncompatibleSemantics("No numerical evaluator")
        if not mp.isfinite(result) or mp.im(result) != 0:
            raise ValueError("Nonfinite or nonreal value omitted")
        return mp.re(result)


def point(project: Project, name: str, x: str, digits: int = 30, *, gamma_factorial=False) -> NumericValue:
    if not 15 <= digits <= 100:
        raise ValueError("Precision must be between 15 and 100 decimal digits")
    with mp.workdps(digits):
        coordinate = mp.mpf(x)
        if not mp.isfinite(coordinate):
            raise ValueError("Coordinate must be finite")
        evaluator = NumericEvaluator(project, name, gamma_factorial=gamma_factorial)
        return NumericValue(mp.nstr(evaluator.at(coordinate), digits), digits)
