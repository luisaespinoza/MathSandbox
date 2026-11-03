"""Parsing helpers for explicit A2 construction syntax."""
import ast
from ..core.ir import Expr, identity

RESERVED = ("IndexedFold", "Tower", "FractionalIntegral", "FractionalDerivative", "Iterate")


def literal(node):
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str) or not node.value:
        raise ValueError("Construction conventions must be explicit nonempty string literals")
    return node.value


def construction(parser, node, scope):
    name = node.func.id
    parse = lambda n: parser.expression(n, scope)
    if name in ("IndexedFold", "Tower"):
        expected = 3 if name == "Tower" else 5
        if len(node.args) != expected:
            raise ValueError("Expected Tower(body, (k, lower, upper), empty) or IndexedFold(body, (k, lower, upper), operation, association, empty)")
        bounds = node.args[1]
        if not isinstance(bounds, ast.Tuple) or len(bounds.elts) != 3 or not isinstance(bounds.elts[0], ast.Name):
            raise ValueError("Fold requires (index, lower, upper)")
        index, lower, upper = bounds.elts
        bound = Expr("symbol", index.id + ":" + identity())
        body = parser.expression(node.args[0], {**scope, index.id: bound})
        if name == "Tower":
            operator, association = "builtin:pow", "right"
        else:
            try:
                operator = parser.registry.named(literal(node.args[2])).id
            except StopIteration:
                raise ValueError("Unknown fold operator") from None
            if parser.registry.definitions[operator].arity != 2:
                raise ValueError("Fold operation must be binary")
            association = literal(node.args[3])
            if association not in ("left", "right"):
                raise ValueError("Fold association must be left or right")
        return Expr("fold", operator, (body, bound, parse(lower), parse(upper), parse(node.args[-1])),
                    (("association", association), ("range", "inclusive-integer")))
    if name in ("FractionalIntegral", "FractionalDerivative"):
        if len(node.args) != 4:
            raise ValueError("Expected FractionalIntegral/Derivative(body, (x, lower), order, definition)")
        bounds = node.args[1]
        if not isinstance(bounds, ast.Tuple) or len(bounds.elts) != 2:
            raise ValueError("Fractional calculus requires (variable, lower)")
        variable, lower = map(parse, bounds.elts)
        if variable.kind != "symbol":
            raise ValueError("Fractional calculus variable must be a bound function parameter")
        method = literal(node.args[3])
        suffix = "integral" if name == "FractionalIntegral" else "derivative"
        rule = {("riemann-liouville", "integral"): "builtin:rl-integral",
                ("riemann-liouville", "derivative"): "builtin:rl-derivative",
                ("caputo", "derivative"): "builtin:caputo-derivative"}.get((method, suffix), method + ":" + suffix)
        return Expr("fractional", rule, (parse(node.args[0]), variable, parse(node.args[2]), lower),
                    (("side", "left"), ("definition", method), ("operation", suffix)))
    if name == "Iterate":
        if len(node.args) != 4 or not isinstance(node.args[0], ast.Name) or node.args[0].id not in parser.names:
            raise ValueError("Expected Iterate(named_function, time, argument, family)")
        return Expr("iterate", parser.names[node.args[0].id], (parse(node.args[1]), parse(node.args[2])),
                    (("family", literal(node.args[3])),))
    raise ValueError("Unknown construction")
