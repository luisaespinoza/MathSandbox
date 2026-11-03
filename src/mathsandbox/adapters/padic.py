"""Exact rational data embedded in Q_p; no approximate real-to-p-adic conversion."""
from dataclasses import asdict
import re
import sympy as sp
from ..core.ir import Context
from ..operators.registry import OperatorRegistry

RATIONAL_CONTEXT = Context(universe_id="standard-rational", domain="Rationals", codomain="Rationals")


def rational(text):
    if not isinstance(text, str) or len(text) > 256 or not re.fullmatch(r"[+-]?\d+(?:/\d+)?", text.strip()):
        raise ValueError("Enter an exact integer or n/d rational (no decimal/float approximation)")
    try:
        value = sp.Rational(text.strip())
    except (ValueError, ZeroDivisionError, TypeError):
        raise ValueError("Invalid exact rational") from None
    if not value.is_Rational or value.q == 0:
        raise ValueError("Invalid exact rational")
    return value


def check_prime(prime):
    if type(prime) is not int or not 2 <= prime <= 97 or not sp.isprime(prime):
        raise ValueError("Choose a prime integer between 2 and 97")


def bounded(value):
    if not value.is_Rational or max(abs(int(value.p)).bit_length(), int(value.q).bit_length()) > 8192:
        raise ValueError("Exact rational result exceeds the bit-size budget")
    return value


class RationalEvaluator:
    def __init__(self, project, name):
        self.project = project
        self.obj = project.objects[project.names[name]]
        context = self.obj.context
        if (context.universe_id != "standard-rational" or context.domain != "Rationals" or context.codomain != "Rationals"
                or not context.precision > 0 or context.assumptions or context.branches != ("principal",) or context.axioms != ("standard-arithmetic",)):
            raise ValueError("p-adic views require the explicit standard-rational input/output context")
        if len(self.obj.parameters) != 1:
            raise ValueError("p-adic views require a single rational parameter")
        self.builtins = OperatorRegistry().definitions

    def at(self, value):
        return self.node(self.obj.expression, {self.obj.parameters[0].value: value})

    def node(self, node, bindings):
        if node.kind == "integer":
            return bounded(sp.Integer(node.value))
        if node.kind == "symbol":
            return bindings[node.value]
        if node.kind == "call":
            obj = self.project.objects[node.value]
            if obj.context != self.obj.context:
                raise ValueError("Rational calls require matching contexts; no implicit p-adic extension")
            values = [self.node(a, bindings) for a in node.args]
            return self.node(obj.expression, {p.value: a for p, a in zip(obj.parameters, values)})
        if node.kind != "operator" or node.value not in ("builtin:add", "builtin:mul", "builtin:pow"):
            raise ValueError("Only rational arithmetic and integer powers have an exact rational evaluator")
        if self.project.registry.definitions.get(node.value) != self.builtins.get(node.value):
            raise ValueError("Custom operations cannot become ordinary rational arithmetic")
        a, b = [self.node(arg, bindings) for arg in node.args]
        if node.value == "builtin:add":
            result = a+b
        elif node.value == "builtin:mul":
            result = a*b
        else:
            if not b.is_Integer or abs(b) > 1024:
                raise ValueError("Rational powers require an integer exponent within the resource budget")
            if a == 0 and b <= 0:
                raise ValueError("Undefined zero power or pole")
            if max(abs(int(a.p)).bit_length(), int(a.q).bit_length())*abs(int(b)) > 8192:
                raise ValueError("Exact power exceeds the bit-size budget")
            result = a**b
        return bounded(result)


def valuation(value, prime):
    check_prime(prime)
    if not getattr(value, "is_Rational", False):
        raise ValueError("Valuation input must be an exact SymPy rational")
    return None if value == 0 else int(sp.multiplicity(prime, value))


def describe(value, prime, digits):
    check_prime(prime)
    if type(digits) is not int or not 1 <= digits <= 8:
        raise ValueError("p-adic precision must be 1..8 base-p digits")
    v = valuation(value, prime)
    unit = value/sp.Integer(prime)**v if v is not None else sp.Integer(0)
    norm = sp.Integer(prime)**(-v) if v is not None else sp.Integer(0)
    modulus = prime**digits
    residue = int(unit.p)*pow(int(unit.q), -1, modulus) % modulus
    expansion = [(residue//prime**i) % prime for i in range(digits)]
    nodes = [{"id": "root", "parent": None, "depth": 0, "residue": 0, "modulus": 1, "x": 0.0, "selected": True}]
    parent, previous, parent_x = "root", 0, 0.0
    for depth in range(1, digits+1):
        mod, step = prime**depth, prime**(depth-1)
        chosen = residue % mod
        selected_node = None
        for digit in range(prime):
            current = previous+digit*step
            x = parent_x+(digit-(prime-1)/2)/step
            node = {"id": f"{depth}:{current}", "parent": parent, "depth": depth, "residue": current,
                    "modulus": mod, "x": x, "selected": current == chosen, "digit": digit}
            nodes.append(node)
            if node["selected"]:
                selected_node = node
        parent, previous, parent_x = selected_node["id"], chosen, selected_node["x"]
    return {"rational": str(value), "valuation": v if v is not None else "infinity", "norm": str(norm),
            "unit_part": str(unit) if value != 0 else None, "unit_residue": residue, "modulus": modulus,
            "digits": expansion, "nodes": nodes, "absolute_precision": v+digits if v is not None else None,
            "reconstruction": "q = p^valuation * unit_part; unit_part known modulo p^precision" if value else "q=0; valuation infinity, norm zero; zero residue path"}


def sample_padic(project, name, settings, geometry, coordinate):
    check_prime(geometry.prime)
    input_value = rational(coordinate)
    evaluator = RationalEvaluator(project, name)
    output = evaluator.at(input_value)
    description = describe(output, geometry.prime, geometry.padic_digits)
    obj = evaluator.obj
    return {"point": {"status": "exact-rational", "value": str(output), "input": str(input_value), "error_estimate": "none: exact rational arithmetic"},
            "plot": {"kind": "padic", "status": "exact-rational-finite-precision", **description,
                     "input": str(input_value), "prime": geometry.prime, "precision": geometry.padic_digits,
                     "input_valuation": valuation(input_value, geometry.prime) if input_value else "infinity",
                     "backend": "SymPy", "backend_version": sp.__version__, "context": asdict(obj.context),
                     "source_id": obj.id, "source_revision": obj.revision,
                     "dependency_revisions": sorted((i, project.objects[i].revision) for i in project.closure(obj.id)),
                     "settings": {**asdict(settings), **asdict(geometry)}, "warnings": [],
                     "error_estimate": "Exact rational/valuation/norm; residue tree truncated at selected base-p precision",
                     "conventions": {"embedding": "canonical embedding of Q into Q_p; no general p-adic function extension",
                                     "topology": "ultrametric residue balls; tree coordinates are diagram layout, not Euclidean distance",
                                     "tree": "unit-part digit path and its siblings; unexpanded subtrees omitted"}}}
