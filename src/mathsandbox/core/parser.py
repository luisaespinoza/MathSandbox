"""A deliberately small parser; no eval, exec, or SymPy string parsing."""
import ast
import re
from .ir import Expr, identity
from ..operators.registry import OperatorRegistry
from ..operators.syntax import RESERVED, construction


class Parser:
    def __init__(self, registry: OperatorRegistry, names: dict[str, str]):
        self.registry, self.names = registry, names

    def definition(self, text: str) -> tuple[str, tuple[Expr, ...], Expr]:
        match = re.fullmatch(r"\s*([A-Za-z_]\w*)\s*\(([^()]*)\)\s*=\s*(.+)", text)
        if not match:
            raise ValueError("Expected name(parameters) = expression")
        name, params, body = match.groups()
        tokens = [p.strip() for p in params.split(",")] if params.strip() else []
        if len(tokens) != len(set(tokens)) or any(not re.fullmatch(r"[A-Za-z_]\w*", p) for p in tokens):
            raise ValueError("Invalid or duplicate parameters")
        scope = {p: Expr("symbol", p + ":" + identity()) for p in tokens}
        return name, tuple(scope.values()), self.expression(ast.parse(body.replace("^", "**"), mode="eval").body, scope)

    def expression(self, node: ast.AST, scope: dict[str, Expr]) -> Expr:
        parse = lambda n: self.expression(n, scope)
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return Expr("integer", str(node.value))
        if isinstance(node, ast.Name):
            if node.id in ("pi", "E", "I") and node.id not in scope:
                return Expr("constant", node.id)
            if node.id not in scope:
                raise ValueError(f"Unbound symbol: {node.id}")
            return scope[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return Expr("operator", "builtin:mul", (Expr("integer", "-1"), parse(node.operand)))
        if isinstance(node, ast.BinOp):
            left, right = parse(node.left), parse(node.right)
            if isinstance(node.op, ast.Sub):
                right = Expr("operator", "builtin:mul", (Expr("integer", "-1"), right))
            if isinstance(node.op, ast.Div):
                right = Expr("operator", "builtin:pow", (right, Expr("integer", "-1")))
            op = {ast.Add: "add", ast.Sub: "add", ast.Mult: "mul", ast.Div: "mul", ast.Pow: "pow"}.get(type(node.op))
            if op:
                return Expr("operator", "builtin:" + op, (left, right))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            name = node.func.id
            if name in RESERVED:
                return construction(self, node, scope)
            if name == "Integral" and len(node.args) == 2:
                bounds = node.args[1]
                if not isinstance(bounds, ast.Tuple) or len(bounds.elts) != 3 or not isinstance(bounds.elts[0], ast.Name):
                    raise ValueError("Expected Integral(body, (variable, lower, upper))")
                variable, lower, upper = bounds.elts
                bound = Expr("symbol", variable.id + ":" + identity())
                body = self.expression(node.args[0], {**scope, variable.id: bound})
                return Expr("integral", "definite", (body, bound, parse(lower), parse(upper)))
            if name == "diff" and len(node.args) == 2:
                variable = parse(node.args[1])
                if variable.kind != "symbol":
                    raise ValueError("Differentiation variable must be a symbol")
                return Expr("derivative", "diff", (parse(node.args[0]), variable))
            args = tuple(parse(a) for a in node.args)
            if name in self.names:
                return Expr("call", self.names[name], args)
            try:
                operator = self.registry.named(name)
            except StopIteration:
                raise ValueError(f"Unknown function: {name}") from None
            if len(args) != operator.arity:
                raise ValueError("Operator arity mismatch")
            return Expr("operator", operator.id, args)
        raise ValueError(f"Unsupported syntax: {ast.dump(node)}")
