# A2 — generalized operators

A2 adds finite indexed folds and a small registry of explicitly selected fractional
calculus and iteration definitions. SymPy evaluates exact expressions; mpmath
samples licensed exact results. This is not a general fractional-calculus solver,
a continuous tetration algorithm, or a new symbolic algebra engine.

## Workbench

Install/update `.[workbench,dev]` and launch `mathsandbox`. The **Power towers**,
**Fractional calculus**, and **Half iteration** example buttons load reproducible
sessions. Select a function to inspect its expression, input domain, and the rules
recorded under Context & provenance. Open the matching JSON in `examples/` to
restore each session as well.

New definitions use real inputs. After applying a branch-sensitive definition,
select that function and explicitly set **Positive real inputs (x > 0)**. Domain
changes are edits: they retain the previous definition/context in history and
invalidate downstream representations. For multi-parameter functions the selected
domain applies to every parameter; mixed parameter domains are not modeled yet.
Negative and zero inputs to positive-domain functions are excluded from plots and
point evaluation. Setting a positive domain does not prove a theorem or change an
unrelated mathematical universe, axiom set, or branch convention.

## Indexed folds

```text
heterogeneous(x) = Tower(k+1, (k, 1, 3), 1)
right(x) = IndexedFold(k+1, (k, 1, 3), "pow", "right", 1)
left(x) = IndexedFold(k+1, (k, 1, 3), "pow", "left", 1)
sum(x) = IndexedFold(k, (k, 1, 5), "add", "left", 0)
product(x) = IndexedFold(k, (k, 1, 5), "mul", "right", 1)
```

The first two return `2^(3^4) = 2^81`; the third returns `(2^3)^4 = 4096`.
Ranges are inclusive integers. `Tower` is a right-associated power fold. The last
argument is the explicitly selected empty-range value, not an inferred identity or
an extra operand for a nonempty range. Thus `Tower(2, (k,1,0), 1)` is 1; heights
1, 2, 3, 4 give 2, 4, 16, 65536. Choosing another empty value changes that convention.

The index is lexically bound only inside the operand. Endpoints and empty values
are evaluated in the surrounding scope. Nested folds and named function calls
retain distinct binding identities. The binary operation is referenced by registry
identity, so a custom `star` remains `star` and never silently becomes multiplication.

Finite evaluation is bounded to 32 terms. Exact power arguments and estimated
integer sizes are limited as well; oversized folds/towers remain formal. Symbolic
or noninteger endpoints remain unevaluated. There is no fractional-height tower
interpolation. A2 handles scalar binary add/multiply/power; custom operations can
be represented and saved without an evaluator. Matrix/set-indexed folds and custom
evaluation trees beyond left/right are deferred.

## Fractional calculus

```text
integral(x) = FractionalIntegral(x^2, (x, 0), 1/2, "riemann-liouville")
rl(x) = FractionalDerivative(1, (x, 0), 1/2, "riemann-liouville")
caputo(x) = FractionalDerivative(1, (x, 0), 1/2, "caputo")
```

Select positive-real inputs for these functions. The rules use the left endpoint
zero and the positive real branch. For a real power `x^beta` with `beta > -1`,
real `alpha > 0`, and `x > 0`:

- Riemann–Liouville integral:
  `Gamma(beta+1)/Gamma(beta+alpha+1) * x^(beta+alpha)`.
- Riemann–Liouville derivative:
  `Gamma(beta+1)/Gamma(beta-alpha+1) * x^(beta-alpha)`.
- Caputo derivative: for noninteger order, `n = ceil(alpha)` must be determined.
  Nonnegative integer powers below n give zero. Other powers require
  `beta > n-1` so the initial n-th derivative is locally integrable. Integer
  orders use the ordinary derivative power rule on `x>0`.

Consequently, the sample integral is `16*x^(5/2)/(15*sqrt(pi))`. The half derivative
of the constant 1 is `1/sqrt(pi*x)` under Riemann–Liouville and 0 under Caputo.
Their definitions and initial conditions are retained separately, including after
save/load. Rules also accept a factor independent of the differentiation variable.

Other functions, endpoints, orders without established admissibility, negative or
complex orders, and unimplemented definitions remain formal. `I` is available to
represent complex-order requests; a real-only backend refuses to certify them.
Exact-rule numerical orders above 128 are retained formally for resource control.
No analytic continuation of these formulas is inferred. General fractional
quadrature, parameter-dependent admissibility solving, and complex branches are
not implemented.

## Iteration

```text
f(x) = x^2
half(x) = Iterate(f, 1/2, x, "positive-power")
twice(x) = half(half(x))
```

Set `half` and `twice` to positive-real inputs (or load the example). The chosen
family is `F_t(x) = x^(p^t)` for `f(x)=x^p`, fixed real `p>0`, and `x>0`.
It gives `half(x)=x^sqrt(2)` and `twice(x)=x^2` exactly. This is an explicitly
selected family, not a claim that discrete iterates uniquely determine it.
`F_0` and `F_1` and the composition law follow within this chosen positive-real
family; the tests check these symbolic identities. Edits to `f` invalidate the
family's dependent representations.

Other registered families are:

| Selection | Recognized base | Defined family |
| --- | --- | --- |
| `translation` | `f(x)=x+c` on all reals, fixed real c | `x+c*t` |
| `positive-scaling` | `f(x)=a*x`, fixed real a>0 | `a^t*x` |
| `integer` | An evaluable unary function | Finite composition, integer times 0..32 |

Fractional/complex time in the integer construction, unrecognized base functions,
unknown families, and unlicensed domains remain unevaluated. Inverse iteration,
arbitrary Abel/Schröder coordinate discovery, numerical interpolation of arbitrary
iterates, and continuous tetration are deferred. A user-defined family can be
registered declaratively and saved; JSON cannot install executable evaluators.

Numerical evaluation of iterates also has a magnitude budget: exponential arguments
and power log-magnitudes beyond one million stop with a warning rather than
allocating unbounded intermediate numbers. The exact expression remains intact.
This budget is a computational limit, not a statement about mathematical existence.

## Records and verification

IR nodes are immutable and record fold association/range, fractional definition
and side, or iteration family. Project schema version 2 stores these conventions,
the declarative construction registry, contexts, revisions, history, and backend
rules/diagnostics. The loader accepts version 1 A0/A1 files and migrates additive
builtins without changing the identity of legacy custom operators. Version 2 files
are intentionally not readable by older releases. Changed builtin descriptions,
contradictory fractional identities, malformed conventions, and dependency cycles
are rejected. Cached results are recomputed after loading.

SymPy checks and simplifies the recognized formulas. Results remain labeled exact
symbolic computations under their recorded context, not independently checked
proof certificates. Numeric sampling and quadrature checks carry no exactness or
consistency certification. No A3 geometry, A4 continuation/PDE tools, or A5 axiom
laboratory is included.

```sh
python examples/generalized_operators.py
python -m pytest -q
```

## Recorded validation

- Python 3.12, SymPy 1.14.0, mpmath 1.3.0, Plotly 6.9.0: all 100 pytest tests passed.
- Checks cover heterogeneous/right/left folds, empty ranges, lexical scope,
  dependency invalidation, RL versus Caputo initial conditions, rejection of
  inadmissible parameters, defining-integral quadrature agreement, exact half
  iteration and additive-time composition, real/positive domain isolation,
  resource guards, and project schema/registry integrity.
- Chromium exercised the three A2 examples, exact and numerical outputs, explicit
  domain revocation/restoration, excluded zero inputs, schema-2 download/reopen,
  and narrow-screen layout. There were no JavaScript page errors or remote asset
  requests. The same browser workflow passed against the installed wheel.
- A noneditable 0.3.0 wheel installed into an isolated environment. Seven focused
  installed-package checks passed for HTTP/assets, the three example sessions,
  half iteration, the fractional power integral, and the numerical magnitude guard.
- `examples/generalized_operators.py` executed successfully, and the source project
  files in `examples/` round-trip through the loader.
