"""Bounded A2 rules, delegated to SymPy arithmetic, gamma, and simplification."""
import sympy as sp
from .sympy_backend import IncompatibleSemantics


def fold(translator, node):
    body, index, lower, upper, empty = node.args
    lower, upper = translator.translate(lower), translator.translate(upper)
    if not isinstance(lower, sp.Integer) or not isinstance(upper, sp.Integer):
        raise IncompatibleSemantics("Fold bounds must be finite integers; symbolic/noninteger bounds stay formal")
    count = int(upper-lower+1)
    if count <= 0:
        translator.rules.append("fold:explicit-empty-convention")
        return translator.translate(empty)
    if count > 32:
        raise IncompatibleSemantics("Finite fold exceeds the 32-term resource budget")
    values = []
    try:
        for k in range(int(lower), int(upper)+1):
            translator.bound_values[index.value] = sp.Integer(k)
            values.append(translator.translate(body))
    finally:
        translator.bound_values.pop(index.value, None)
    association = dict(node.conventions)["association"]
    if association == "right":
        result = values[-1]
        for value in reversed(values[:-1]):
            result = translator.operation(node.value, (value, result))
    else:
        result = values[0]
        for value in values[1:]:
            result = translator.operation(node.value, (result, value))
    translator.rules.append("fold:" + association + ":inclusive-integer")
    return result


def fractional(translator, node):
    if not translator.constructions.licensed(node.value, "fractional"):
        raise IncompatibleSemantics("No licensed evaluator for this fractional-calculus definition")
    body, variable, order, lower = node.args
    x = translator.symbol(variable)
    alpha = translator.translate(order)
    lower = translator.translate(lower)
    if translator.context.domain != "PositiveReals" or x.is_positive is not True:
        raise IncompatibleSemantics("Fractional power rules require the explicit PositiveReals input domain (x>0)")
    if lower != 0 or alpha.is_real is not True or alpha.is_positive is not True:
        raise IncompatibleSemantics("This rule requires lower endpoint 0 and real order > 0")
    if alpha.is_number and alpha > 128:
        raise IncompatibleSemantics("Fractional order exceeds the exact-rule resource budget")
    value = translator.translate(body)
    coefficient, power = value.as_independent(x, as_Add=False)
    if power == 1:
        beta = sp.Integer(0)
    elif power == x:
        beta = sp.Integer(1)
    elif power.is_Pow and power.base == x and not power.exp.has(x):
        beta = power.exp
    else:
        raise IncompatibleSemantics("Fractional evaluator currently supports coefficient times a single power of x")
    if beta.is_real is not True or (beta+1).is_positive is not True:
        raise IncompatibleSemantics("Power rule needs real exponent beta > -1 for integrability at zero")
    if node.value == "builtin:rl-integral":
        result = coefficient*sp.gamma(beta+1)/sp.gamma(beta+alpha+1)*x**(beta+alpha)
        rule = "Riemann-Liouville:I_0+^alpha(x^beta); alpha>0,beta>-1,x>0"
    else:
        if node.value == "builtin:caputo-derivative":
            # For noninteger alpha, n=ceil(alpha) must be established and the
            # n-th derivative locally integrable at the lower endpoint.
            if alpha.is_integer is not True:
                n = sp.ceiling(alpha)
                if not isinstance(n, sp.Integer):
                    raise IncompatibleSemantics("Caputo rule requires a determined derivative order ceil(alpha)")
                if beta.is_integer is True and beta.is_nonnegative is True and (beta < n) is sp.true:
                    translator.rules.append("Caputo:annihilates-polynomials-below-ceil(alpha)")
                    return sp.Integer(0)
                if (beta-n+1).is_positive is not True:
                    raise IncompatibleSemantics("Caputo power lacks the required integrable initial derivative")
        result = coefficient*sp.gamma(beta+1)/sp.gamma(beta-alpha+1)*x**(beta-alpha)
        rule = ("Caputo" if node.value == "builtin:caputo-derivative" else "Riemann-Liouville") + ":D_0+^alpha(x^beta); x>0,integrability-checked"
    translator.rules.append(rule)
    return sp.simplify(result)


def iterate(translator, node):
    family = dict(node.conventions)["family"]
    if not translator.constructions.licensed(family, "iteration"):
        raise IncompatibleSemantics("Iteration requires a registered, explicitly selected construction")
    obj = translator.objects[node.value]
    time, argument = (translator.translate(arg) for arg in node.args)
    translator.check_call(obj, (argument,))
    parameter = translator.symbol(obj.parameters[0])
    if family == "integer":
        if not isinstance(time, sp.Integer) or not 0 <= time <= 32:
            raise IncompatibleSemantics("Integer iteration supports times 0..32; no automatic fractional interpolation")
        result = argument
        for _ in range(int(time)):
            result = translator.apply_function(obj, (result,))
        translator.rules.append("iterate:finite-nonnegative-composition")
        return result
    if time.is_real is not True:
        raise IncompatibleSemantics("A2 continuous families require real time; complex extension remains formal")
    body = translator.translate(obj.expression).doit()
    if family == "positive-power":
        if argument.is_positive is not True:
            raise IncompatibleSemantics("Positive-power iteration requires an explicitly positive argument")
        exponent = sp.Integer(1) if body == parameter else body.exp if body.is_Pow and body.base == parameter else None
        if exponent is None or exponent.has(parameter) or exponent.is_positive is not True or exponent.is_real is not True:
            raise IncompatibleSemantics("Selected family only applies to f(x)=x^p with fixed real p>0")
        translator.rules.append("iterate:chosen-positive-power-family;x>0,p>0,F_t=x^(p^t)")
        height = translator.operation("builtin:pow", (exponent, time))
        return translator.operation("builtin:pow", (argument, height))
    if family == "translation":
        shift = sp.simplify(body-parameter)
        if obj.context.domain != "Reals" or shift.has(parameter) or shift.is_real is not True:
            raise IncompatibleSemantics("Translation family requires f(x)=x+c on all reals")
        translator.rules.append("iterate:translation;F_t=x+c*t")
        return argument+shift*time
    if family == "positive-scaling":
        scale = sp.simplify(body/parameter)
        if scale.has(parameter) or scale.is_positive is not True or scale.is_real is not True:
            raise IncompatibleSemantics("Scaling family requires f(x)=a*x with real a>0")
        translator.rules.append("iterate:positive-scaling;F_t=a^t*x")
        return translator.operation("builtin:pow", (scale, time))*argument
    raise IncompatibleSemantics("Unsupported iteration family")
