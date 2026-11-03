"""Conservative translation into standard real SymPy semantics."""
import multiprocessing as mp
import sympy as sp
from ..core.ir import Context, Expr, MathObject
from ..operators.registry import OperatorRegistry
from ..operators.constructions import ConstructionRegistry


class IncompatibleSemantics(ValueError):
    pass


def compatible(context: Context) -> bool:
    return (context.universe_id == "standard-real" and context.domain in ("Reals", "PositiveReals")
            and context.codomain == "Reals" and not context.assumptions
            and context.branches == ("principal",)
            and context.axioms == ("standard-arithmetic",) and context.precision > 0)


class Translator:
    def __init__(self, objects: dict[str, MathObject], registry: OperatorRegistry, context: Context, constructions=None):
        self.objects, self.registry, self.context = objects, registry, context
        self.symbols: dict[str, sp.Symbol] = {}
        self.bound_values = {}
        self.rules = []
        self.constructions = constructions if constructions is not None else ConstructionRegistry()

    def symbol(self, node: Expr) -> sp.Symbol:
        if node.value not in self.symbols:
            positive = any(obj.context.domain == "PositiveReals" and node in obj.parameters for obj in self.objects.values())
            self.symbols[node.value] = sp.Dummy(node.value.split(":")[0], positive=True) if positive else sp.Dummy(node.value.split(":")[0], real=True)
        return self.symbols[node.value]

    def translate(self, node: Expr) -> sp.Expr:
        if node.kind in ("fold", "fractional", "iterate"):
            from . import a2_rules
            return getattr(a2_rules, node.kind)(self, node)
        if node.kind == "constant":
            if node.value == "I":
                raise IncompatibleSemantics("Complex constants remain formal in the real-only backend")
            return {"pi": sp.pi, "E": sp.E, "I": sp.I}[node.value]
        if node.kind == "integer":
            return sp.Integer(node.value)
        if node.kind == "symbol":
            return self.bound_values.get(node.value, self.symbol(node))
        if node.kind == "call":
            obj = self.objects[node.value]
            return self.apply_function(obj, tuple(self.translate(a) for a in node.args))
        if node.kind == "integral":
            body, variable, lower, upper = node.args
            return sp.Integral(self.translate(body), (self.symbol(variable), self.translate(lower), self.translate(upper)))
        if node.kind == "derivative":
            return sp.Derivative(self.translate(node.args[0]), self.symbol(node.args[1]))
        if node.kind == "operator":
            return self.operation(node.value, tuple(self.translate(a) for a in node.args))
        raise IncompatibleSemantics("Unsupported IR node")

    def check_call(self, obj, args):
        from dataclasses import replace
        if (not compatible(obj.context) or replace(obj.context, domain=self.context.domain) != self.context
                or len(args) != len(obj.parameters)):
            raise IncompatibleSemantics("Function context or arity mismatch")
        if obj.context.domain == "PositiveReals" and any(a.is_positive is not True for a in args):
            raise IncompatibleSemantics("Function call does not establish its positive input domain")

    def apply_function(self, obj, args):
        self.check_call(obj, args)
        body = self.reconstruct(self.translate(obj.expression).doit())
        previous = self.bound_values.copy()
        self.bound_values.update({p.value: a for p, a in zip(obj.parameters, args)})
        try:
            return self.translate(body)
        finally:
            self.bound_values = previous

    def operation(self, identity, args):
        definition = self.registry.definitions[identity]
        functions = {"add": sp.Add, "mul": sp.Mul, "pow": sp.Pow, "sin": sp.sin, "cos": sp.cos,
                     "exp": sp.exp, "log": sp.log, "factorial": sp.factorial, "gamma": sp.gamma}
        name = identity.removeprefix("builtin:")
        if (identity != "builtin:" + name or name not in functions
                or definition.semantics != "standard:" + name or definition.universe_id != self.context.universe_id):
            raise IncompatibleSemantics("No licensed backend evaluator for operator")
        if name in ("factorial", "gamma") and args[0].is_number and abs(args[0]) > 4096:
            raise IncompatibleSemantics("Special-function argument exceeds the resource budget")
        if name == "factorial" and not (isinstance(args[0], sp.Integer) and args[0] >= 0):
            raise IncompatibleSemantics("Symbolic factorial needs an explicit extension")
        if name == "gamma" and not (args[0].is_positive is True or (args[0].is_real is True and args[0].is_integer is False)):
            raise IncompatibleSemantics("Gamma argument must be known real and away from its poles")
        if name == "log" and args[0].is_positive is not True:
            raise IncompatibleSemantics("Logarithm needs a licensed positive domain")
        if name == "pow":
            base, exponent = args
            if not isinstance(exponent, sp.Integer) and base.is_positive is not True:
                raise IncompatibleSemantics("Noninteger powers need a licensed positive base")
            if exponent.is_negative is True and base.is_nonzero is not True:
                raise IncompatibleSemantics("Reciprocal needs a nonzero-domain obligation")
            if base.is_zero is True and exponent.is_nonpositive is True:
                raise IncompatibleSemantics("Undefined zero power")
            if isinstance(exponent, sp.Integer):
                if abs(exponent) > 4096 or (isinstance(base, sp.Integer) and exponent > 0 and int(abs(base)).bit_length()*int(exponent) > 8192):
                    raise IncompatibleSemantics("Exact power exceeds the resource budget")
        return functions[name](*args)

    def reconstruct(self, value: sp.Expr) -> Expr:
        reverse = {symbol: key for key, symbol in self.symbols.items()}
        if value == sp.I:
            return Expr("constant", "I")
        if value == sp.pi:
            return Expr("constant", "pi")
        if value == sp.E:
            return Expr("constant", "E")
        if value in reverse:
            return Expr("symbol", reverse[value])
        if isinstance(value, sp.Integer):
            return Expr("integer", str(value))
        if isinstance(value, sp.Rational):
            return Expr("operator", "builtin:mul", (Expr("integer", str(value.p)), Expr("operator", "builtin:pow", (Expr("integer", str(value.q)), Expr("integer", "-1")))))
        functions = {sp.Add: "add", sp.Mul: "mul", sp.Pow: "pow", sp.sin: "sin", sp.cos: "cos", sp.exp: "exp", sp.log: "log", sp.gamma: "gamma"}
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


def _worker(connection, expression, objects, registry, context, constructions):
    try:
        translator = Translator(objects, registry, context, constructions)
        value = sp.trigsimp(translator.translate(expression).doit())
        if value.is_real is False:
            raise IncompatibleSemantics("Nonreal result is incompatible with the declared real codomain")
        if value.has(sp.Integral, sp.Derivative):
            connection.send((expression, "unevaluated", (), "Backend retained an unevaluated operation"))
        else:
            result = translator.reconstruct(value)
            translator.translate(result)  # Validate the reconstructed IR against the same registry/domain.
            connection.send((result, "exact", tuple(dict.fromkeys(translator.rules)), ""))
    except Exception as error:
        # Failure preserves the source; it never fabricates an exact result.
        connection.send((expression, "unevaluated", (), str(error) or type(error).__name__))
    finally:
        connection.close()


def evaluate(expression: Expr, objects: dict[str, MathObject], registry: OperatorRegistry,
             context: Context, timeout: float = 10.0, constructions=None) -> tuple[Expr, str, tuple[str, ...], str]:
    if not compatible(context):
        return expression, "unevaluated", (), "Context is not licensed by the SymPy adapter"
    runtime = mp.get_context("spawn")
    reader, writer = runtime.Pipe(duplex=False)
    process = runtime.Process(target=_worker, args=(writer, expression, objects, registry, context, constructions))
    process.start()
    writer.close()
    try:
        if reader.poll(timeout):
            try:
                return reader.recv()
            except EOFError:
                pass
        return expression, "unevaluated", (), "Backend timed out or exited without a result"
    finally:
        reader.close()
        if process.is_alive():
            process.terminate()
        process.join()
