"""Conservative translation into standard real SymPy semantics."""
import multiprocessing as mp
import sympy as sp
from ..core.ir import Context, Expr, MathObject
from ..operators.registry import OperatorRegistry


class IncompatibleSemantics(ValueError):
    pass


def compatible(context: Context) -> bool:
    return (context.universe_id == "standard-real" and context.domain == "Reals"
            and context.codomain == "Reals" and not context.assumptions
            and context.branches == ("principal",)
            and context.axioms == ("standard-arithmetic",) and context.precision > 0)


class Translator:
    def __init__(self, objects: dict[str, MathObject], registry: OperatorRegistry, context: Context):
        self.objects, self.registry, self.context = objects, registry, context
        self.symbols: dict[str, sp.Symbol] = {}

    def symbol(self, node: Expr) -> sp.Symbol:
        if node.value not in self.symbols:
            self.symbols[node.value] = sp.Dummy(node.value.split(":")[0], real=True)
        return self.symbols[node.value]

    def translate(self, node: Expr) -> sp.Expr:
        if node.kind == "integer":
            return sp.Integer(node.value)
        if node.kind == "symbol":
            return self.symbol(node)
        if node.kind == "call":
            obj = self.objects[node.value]
            if obj.context != self.context or len(node.args) != len(obj.parameters):
                raise IncompatibleSemantics("Function context or arity mismatch")
            body = self.translate(obj.expression)
            # Unique parameter/binder identities and simultaneous replacement avoid capture.
            return body.doit().xreplace({self.symbol(p): self.translate(a) for p, a in zip(obj.parameters, node.args)})
        if node.kind == "integral":
            body, variable, lower, upper = node.args
            return sp.Integral(self.translate(body), (self.symbol(variable), self.translate(lower), self.translate(upper)))
        if node.kind == "derivative":
            return sp.Derivative(self.translate(node.args[0]), self.symbol(node.args[1]))
        if node.kind == "operator":
            definition = self.registry.definitions[node.value]
            functions = {"add": sp.Add, "mul": sp.Mul, "pow": sp.Pow, "sin": sp.sin, "cos": sp.cos, "exp": sp.exp, "log": sp.log}
            name = node.value.removeprefix("builtin:")
            if (node.value != "builtin:" + name or name not in functions
                    or definition.semantics != "standard:" + name
                    or definition.universe_id != self.context.universe_id):
                raise IncompatibleSemantics("No licensed backend evaluator for operator")
            args = tuple(self.translate(a) for a in node.args)
            # A0 does not yet model exceptional sets or prove positivity. Refuse
            # transformations that could erase a pole or select a complex branch.
            if name == "log":
                raise IncompatibleSemantics("Logarithm needs a licensed domain")
            if name == "pow":
                base, exponent = args
                if not isinstance(exponent, sp.Integer):
                    raise IncompatibleSemantics("Noninteger powers need branch/domain obligations")
                if exponent < 0 and (base.free_symbols or base.is_zero is not False):
                    raise IncompatibleSemantics("Reciprocal needs a nonzero-domain obligation")
            return functions[name](*args)
        raise IncompatibleSemantics("Unsupported IR node")

    def reconstruct(self, value: sp.Expr) -> Expr:
        reverse = {symbol: key for key, symbol in self.symbols.items()}
        if value in reverse:
            return Expr("symbol", reverse[value])
        if isinstance(value, sp.Integer):
            return Expr("integer", str(value))
        if isinstance(value, sp.Rational):
            return Expr("operator", "builtin:mul", (Expr("integer", str(value.p)), Expr("operator", "builtin:pow", (Expr("integer", str(value.q)), Expr("integer", "-1")))))
        functions = {sp.Add: "add", sp.Mul: "mul", sp.Pow: "pow", sp.sin: "sin", sp.cos: "cos", sp.exp: "exp", sp.log: "log"}
        if value.func in functions:
            args = tuple(self.reconstruct(a) for a in value.args)
            name = functions[value.func]
            if name in ("add", "mul"):
                result = args[0]
                for arg in args[1:]:
                    result = Expr("operator", "builtin:" + name, (result, arg))
                return result
            return Expr("operator", "builtin:" + name, args)
        raise IncompatibleSemantics("Backend result requires unsupported IR constructs")


def _worker(connection, expression, objects, registry, context):
    try:
        translator = Translator(objects, registry, context)
        value = sp.trigsimp(translator.translate(expression).doit())
        if value.has(sp.Integral, sp.Derivative):
            connection.send((expression, "unevaluated"))
        else:
            connection.send((translator.reconstruct(value), "exact"))
    except Exception:
        # Failure preserves the source; it never fabricates an exact result.
        connection.send((expression, "unevaluated"))
    finally:
        connection.close()


def evaluate(expression: Expr, objects: dict[str, MathObject], registry: OperatorRegistry,
             context: Context, timeout: float = 10.0) -> tuple[Expr, str]:
    if not compatible(context):
        return expression, "unevaluated"
    runtime = mp.get_context("spawn")
    reader, writer = runtime.Pipe(duplex=False)
    process = runtime.Process(target=_worker, args=(writer, expression, objects, registry, context))
    process.start()
    writer.close()
    try:
        if reader.poll(timeout):
            try:
                return reader.recv()
            except EOFError:
                pass
        return expression, "unevaluated"
    finally:
        reader.close()
        if process.is_alive():
            process.terminate()
        process.join()
