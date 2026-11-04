"""Restricted semantic translation for A4, using SymPy rather than string eval."""
import re
import sympy as sp
import mpmath as mp
from ..core.ir import Context
from ..adapters.sympy_backend import Translator, compatible as real_context
from ..adapters.complex_numeric import compatible as complex_context
from ..operators.registry import OperatorRegistry


def number(text):
    if not isinstance(text, str) or len(text) > 100 or not re.fullmatch(r"[+-]?(?:\d+(?:/\d+|\.\d*)?|\.\d+)", text.strip()):
        raise ValueError("Coordinates must be exact integer, rational, or finite decimal strings")
    try:
        value = sp.Rational(text.strip())
    except Exception:
        raise ValueError("Invalid coordinate") from None
    if not value.is_finite or abs(value) > 100:
        raise ValueError("Analysis coordinates are bounded to ±100")
    return value


def center(real="0", imaginary="0"):
    return number(real)+sp.I*number(imaginary)


def numeric(value, digits):
    result = mp.mpc(mp.mpf(str(sp.re(value).evalf(digits))), mp.mpf(str(sp.im(value).evalf(digits))))
    if not mp.isfinite(result):
        raise ValueError("Nonfinite analytic coefficient or coordinate")
    return result


class Compiler:
    def __init__(self, project, name):
        self.project = project
        self.obj = project.objects[project.names[name]]
        if not (real_context(self.obj.context) or complex_context(self.obj.context)):
            raise ValueError("A4 requires a licensed standard real or principal complex context")
        self.symbols = {}
        for obj in project.objects.values():
            for parameter in obj.parameters:
                options = {"positive": True} if obj.context.domain == "PositiveReals" else {"real": True} if obj.context.domain == "Reals" else {}
                self.symbols[parameter.value] = sp.Dummy(parameter.value.split(":")[0], **options)
        self.exclusions = []
        self.branchful = False
        self.branch_exclusions = []
        self.builtins = OperatorRegistry().definitions
        self.expression = self.convert(self.obj.expression)
        if self.expression.has(sp.nan, sp.zoo, sp.oo, -sp.oo):
            raise ValueError("Undefined or nonfinite source cannot be analyzed")

    @property
    def parameters(self):
        return [self.symbols[p.value] for p in self.obj.parameters]

    def convert(self, node, bindings=None):
        bindings = {} if bindings is None else bindings
        if node.kind == "integer":
            return sp.Integer(node.value)
        if node.kind == "constant":
            if node.value == "I" and not complex_context(self.obj.context):
                raise ValueError("Complex constants require the explicit complex context")
            return {"pi": sp.pi, "E": sp.E, "I": sp.I}[node.value]
        if node.kind == "symbol":
            return bindings[node.value] if node.value in bindings else self.symbols[node.value]
        if node.kind == "call":
            obj = self.project.objects[node.value]
            if obj.context != self.obj.context:
                raise ValueError("A4 named calls require matching explicit contexts")
            values = [self.convert(arg, bindings) for arg in node.args]
            return self.convert(obj.expression, {p.value: value for p, value in zip(obj.parameters, values)})
        if node.kind != "operator":
            raise ValueError("This IR construction has no A4 symbolic adapter; source retained")
        if node.value not in self.builtins or self.project.registry.definitions.get(node.value) != self.builtins[node.value]:
            raise ValueError("Custom operators cannot become standard SymPy operations")
        operation = node.value.removeprefix("builtin:")
        args = [self.convert(arg, bindings) for arg in node.args]
        if operation == "pow":
            base, exponent = args
            if exponent.is_Integer:
                if abs(exponent) > 64:
                    raise ValueError("A4 integer power exceeds its resource budget")
                if exponent < 0:
                    if base == 0:
                        raise ValueError("Source contains an undefined zero power")
                    if base.free_symbols:
                        self.exclusions.append(base)
            else:
                self.branchful = self.branchful or bool(base.free_symbols)
                if base.free_symbols:
                    self.branch_exclusions.append("Principal power cut/branch-point preimage excluded: "+self.display(base))
                if not complex_context(self.obj.context) and base.is_positive is not True:
                    raise ValueError("Noninteger powers require a licensed branch/domain")
            return sp.Pow(base, exponent)
        if operation in ("add", "mul"):
            return (sp.Add if operation == "add" else sp.Mul)(*args)
        if operation in ("sin", "cos", "exp", "log"):
            if operation == "log":
                self.branchful = self.branchful or bool(args[0].free_symbols)
                if args[0].free_symbols:
                    self.branch_exclusions.append("Principal logarithm cut and zero preimage excluded: "+self.display(args[0]))
                if not complex_context(self.obj.context) and args[0].is_positive is not True:
                    raise ValueError("Logarithm requires an explicit admissible branch/domain")
            return getattr(sp, operation)(args[0])
        raise ValueError("This operator is outside the initial A4 symbolic subset")

    def reconstruct(self, value):
        translator = Translator(self.project.objects, self.project.registry, self.obj.context)
        translator.symbols = self.symbols
        return translator.reconstruct(value)

    def display(self, value):
        return str(value.xreplace({symbol: sp.Symbol(symbol.name) for symbol in value.free_symbols}))

    def source_exclusions(self):
        return tuple(dict.fromkeys([self.display(value)+" = 0" for value in self.exclusions]+self.branch_exclusions))

    def analytic_source(self):
        if not complex_context(self.obj.context) or len(self.parameters) != 1:
            raise ValueError("Analytic germs require one parameter and the explicit principal complex context")
        z = self.parameters[0]
        if self.branchful:
            raise ValueError("Branched/Puiseux/logarithmic germs are not supported; branch semantics retained")
        for function in self.expression.atoms(sp.Function):
            if function.func not in (sp.sin, sp.cos, sp.exp) or not function.args[0].is_polynomial(z):
                raise ValueError("Only rational functions and meromorphic combinations of elementary entire polynomial templates are supported")
            if sp.Poly(function.args[0], z).degree() > 8:
                raise ValueError("Entire-function template degree exceeds the budget")
        roots = []
        for exclusion in self.exclusions:
            numerator = sp.fraction(sp.together(exclusion))[0]
            poly = sp.Poly(numerator, z)
            if poly.is_zero:
                raise ValueError("Source is undefined on the entire domain")
            if poly.degree() > 4:
                raise ValueError("Source-exclusion root isolation is bounded to degree four")
            found = sp.roots(poly, z)
            if sum(found.values()) != poly.degree():
                raise ValueError("Cannot establish the complete source-exclusion set")
            roots.extend(found)
        return z, tuple(dict.fromkeys(roots))
