"""Pointwise complex IR evaluation with explicit principal-branch diagnostics."""
import mpmath as mp
from .sympy_backend import Translator
from ..core.ir import Context
from ..operators.registry import OperatorRegistry

COMPLEX_CONTEXT = Context(universe_id="standard-complex", domain="Complexes", codomain="Complexes")


def compatible(context):
    return (context.universe_id == "standard-complex" and context.domain == "Complexes"
            and context.codomain == "Complexes" and not context.assumptions
            and context.branches == ("principal",) and context.axioms == ("standard-arithmetic",)
            and context.precision > 0)


class ComplexEvaluator:
    def __init__(self, project, name, *, gamma_factorial=False):
        self.project = project
        self.obj = project.objects[project.names[name]]
        if not compatible(self.obj.context):
            raise ValueError("Complex views require an explicit standard-complex context with principal branches")
        if len(self.obj.parameters) != 1:
            raise ValueError("Complex views require a single complex parameter")
        self.gamma_factorial = gamma_factorial
        self.builtins = OperatorRegistry().definitions
        self.integer_powers = {}
        self.branches = []
        self.on_cut = False

    def at(self, z):
        self.branches, self.on_cut = [], False
        result = self.node(self.obj.expression, {self.obj.parameters[0].value: mp.mpc(z)})
        if not mp.isfinite(result):
            raise ValueError("Nonfinite complex value omitted; singularity type is not certified")
        return mp.mpc(result)

    def integer_power(self, node):
        if node not in self.integer_powers:
            try:
                value = Translator(self.project.objects, self.project.registry, Context()).translate(node)
                self.integer_powers[node] = not value.free_symbols and value.is_integer is True
            except Exception:
                self.integer_powers[node] = False
        return self.integer_powers[node]

    def branch(self, argument):
        if argument == 0:
            self.branches.append(None)
            self.on_cut = True
        else:
            self.branches.append(float(mp.arg(argument)))
            if mp.im(argument) == 0 and mp.re(argument) < 0:
                self.on_cut = True

    def node(self, node, bindings):
        if node.kind == "integer":
            return mp.mpc(node.value)
        if node.kind == "constant":
            return {"pi": mp.pi, "E": mp.e, "I": mp.j}[node.value]
        if node.kind == "symbol":
            return bindings[node.value]
        if node.kind == "call":
            obj = self.project.objects[node.value]
            if obj.context != self.obj.context:
                raise ValueError("Complex function calls require matching explicit contexts; no automatic complex extension")
            args = [self.node(a, bindings) for a in node.args]
            return self.node(obj.expression, {p.value: a for p, a in zip(obj.parameters, args)})
        if node.kind != "operator":
            raise ValueError("This construction has no complex numerical evaluator; definition retained")
        if self.project.registry.definitions.get(node.value) != self.builtins.get(node.value) or node.value not in self.builtins:
            raise ValueError("Custom operators have no licensed complex evaluator")
        name = node.value.removeprefix("builtin:")
        args = [self.node(a, bindings) for a in node.args]
        if name == "add":
            result = args[0]+args[1]
        elif name == "mul":
            result = args[0]*args[1]
        elif name == "pow":
            base, exponent = args
            if base == 0 and (mp.im(exponent) != 0 or mp.re(exponent) <= 0):
                raise ValueError("Undefined zero power or pole omitted")
            if not self.integer_power(node.args[1]):
                self.branch(base)
            if base != 0 and abs(exponent*mp.log(base)) > 1_000_000:
                raise OverflowError("Complex power exceeds the magnitude budget")
            result = mp.power(base, exponent)
        elif name == "log":
            if args[0] == 0:
                raise ValueError("Logarithmic singularity omitted")
            self.branch(args[0])
            result = mp.log(args[0])
        elif name in ("sin", "cos", "exp"):
            if abs(args[0]) > 1_000_000:
                raise OverflowError("Complex function argument exceeds the budget")
            result = getattr(mp, name)(args[0])
        elif name == "gamma":
            if abs(args[0]) > 10_000:
                raise OverflowError("Complex Gamma argument exceeds the budget")
            result = mp.gamma(args[0])
        elif name == "factorial":
            x = args[0]
            if not self.gamma_factorial and (mp.im(x) != 0 or mp.re(x) < 0 or mp.re(x) != mp.floor(mp.re(x))):
                raise ValueError("Complex factorial needs an explicitly selected extension (not implemented in A3)")
            if mp.im(x) != 0 or mp.re(x) < 0:
                raise ValueError("The selected factorial extension covers nonnegative real arguments only")
            if abs(x) > 10_000:
                raise OverflowError("Factorial argument exceeds the budget")
            result = mp.gamma(x+1)
        else:
            raise ValueError("No complex operator evaluator")
        if not mp.isfinite(result):
            raise ValueError("Nonfinite complex value omitted")
        return result
