# MathSandbox — A1 local workbench

A local browser workbench and Python library for named mathematical definitions,
exact symbolic composition, numerical exploration, and reproducible project records. The project specification is in
[docs/ALPHA_SPEC.md](docs/ALPHA_SPEC.md). This implementation includes A0 and the minimal A1 workbench; A2–A5 remain deferred.

## Install and run

Requires Python 3.11+ and SymPy 1.13–1.x (tested with Python 3.12 and SymPy 1.14).
From this checkout:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[workbench,dev]'
mathsandbox
# After closing the workbench (Ctrl+C in its terminal):
python examples/composition.py
python -m pytest -q
```

Installation needs access to PyPI; normal use needs no network or account.
SymPy (BSD license) performs symbolic algebra and uses mpmath; pytest is only a
development dependency. The optional `workbench` extra supplies Plotly (MIT
license), with all JavaScript served from its installed package. No desktop GUI
toolkit, CDN, account, or external proof tool is needed. The math library alone
can still be installed with `python -m pip install -e '.[dev]'`.

The example defines:

```python
from mathsandbox import Project, save, load

# Run backend operations inside a main guard in scripts (spawned worker process).
def main():
    project = Project()
    project.define("f(x) = x^3")
    project.define("g(x) = sin(x)")
    project.define("h(x) = Integral(f(g(t)), (t, 0, x))")
    project.define("p(x) = diff(h(x), x)")
    print(project.to_sympy("h"))
    print(project.to_sympy("p"))
    save(project, "session.json")
    project = load("session.json")
    project.define("g(x) = sin(2*x)")
    print(project.to_sympy("p"))

if __name__ == "__main__":
    main()
```

Results are exactly `2/3 - cos(x) + cos(x)^3/3` and `sin(x)^3`.
After changing `g`, the derivative becomes `sin(2*x)^3`. SymPy may choose an algebraically equivalent factored or expanded form and print dummy
symbols as `_x`; their unique identities protect lexical bindings.


## Use the workbench

Run `mathsandbox` from your activated Python 3.11+ environment. It opens a local
browser window and binds only to loopback. `mathsandbox --no-browser --port 8766`
is available if you prefer to open the printed address manually. Ctrl+C stops the
server. Use one browser tab per running session; multiple tabs share its project.

- Start with the composition example. Change `g(x) = sin(x)` to
  `g(x) = sin(2*x)` and click **Apply definitions**. The selected dependent function
  and plot refresh automatically. All lines apply atomically; invalid syntax or a
  cyclic dependency leaves the previous project intact. Omitted definitions are
  retained, so clearing a line does not delete a function.
- Select a named function and choose **Exact symbolic**, **Numeric value**, or
  **Keep unevaluated**. Numeric mode evaluates at the given decimal coordinate;
  precision is 15–100 decimal digits. An exact result and a numerical result have
  separate labels. Precision is working precision, not a certified error bound.
  Keep-unevaluated mode displays the original definition and disables computation
  of numeric values and plots.
- Set finite lower/upper bounds. Zoom, pan, and hover in the chart. Hover always
  shows original values even when the coordinates are transformed. **Ordinary
  axes** restores both axes in one click without changing definitions.
- **Save project** downloads versioned JSON, including current definitions,
  history, symbolic provenance, and workbench view/precision/extension settings.
  Pending editor changes are applied before saving. **Open project** accepts A0
  projects and A1 exports. Invalid imports leave the session intact. Sample arrays
  and point values are recomputed on open rather than trusted as certificates.
  There is no autosave; save before closing or replacing the session.

The interface and plotting assets work offline after installation. Projects remain
on your computer; this is a single-session development application, not a hosted
service. Only one-parameter real functions are plottable in A1. No A2 indexed fold,
fractional calculus, or continuous iteration functionality is included.

### Coordinate views and factorial convention

Both axes support these explicit view transforms:

| View | Coordinate | Admissible values |
| --- | --- | --- |
| Linear | `y` | Finite real values |
| Log | `log10(y)` | `y > 0` |
| Symlog | `sign(y) * log10(1 + abs(y))` | Finite real values; fixed unit threshold |
| Factorial | Inverse of `Gamma(t+1)` on `t >= 1` | `y >= 1` |

Factorial coordinates select a monotone inverse branch explicitly: both `0!` and
`1!` are 1, and this branch maps 1 to 1. These are numerical display coordinates,
not a new operation on the source object.

`factorial(x)` is exact for nonnegative integer arguments. To sample it between
integers, explicitly select **Use factorial(x) = Gamma(x+1) for real x ≥ 0**. The
factorial example selects this convention visibly and plots `1 <= x <= 30`.
Without that selection, noninteger factorial arguments remain undefined in the
numerical adapter. The choice is recorded in saved view settings and numerical
plot metadata, and never silently modifies the symbolic definition.

Sampling uses mpmath at the selected precision, then converts transformed display
coordinates to ordinary floating point for Plotly. It refines intervals according
to interpolation error in the selected coordinates, with bounded depth, sample
budget, and a worker timeout. Invalid domains and unresolved steep changes produce
separate curve segments. Overflow, underflow, excluded values, and budget exhaustion
produce warnings. Large magnitudes suggest alternative scales; scales never change
automatically. This is heuristic sampling, not a proof of continuity, a global
error estimate, or guaranteed detection of every narrow feature or singularity.

The numerical adapter evaluates the original IR pointwise when no exact
representation exists: e.g. `1/x` can be sampled away from zero while `x/x` remains
undefined at zero. It never uses symbolic cancellation to widen a domain. Custom
operators/contexts remain unsupported. An integral or derivative requires a licensed
exact symbolic representation before numerical sampling; there is no new numerical
integration or differentiation algorithm in A1.

## A0 contracts

- `core/ir.py`: frozen, typed expression records and context, separate from SymPy.
  Objects keep stable IDs, original definitions, revisions, domains, codomains,
  universe, assumptions, branch conventions, axioms, and precision.
- `core/parser.py`: a restricted Python-AST grammar, never `eval` or SymPy string
  parsing. Supports integer/rational arithmetic, `^` or `**`, unary minus, named
  function calls, sin/cos/exp/log, factorial, definite `Integral`, and first `diff`.
  All symbols must be parameters or lexically bound integral variables. Function
  parameters and integral binders have distinct identities; substitution is
  simultaneous. Float literals, attributes, keyword calls, and arbitrary Python
  are rejected.
- `operators/`: identity-based extensible registry. Custom operator definitions
  retain identity, notation, arity, universe, and semantic description. They can
  be parsed and serialized, but have no licensed evaluator in the A0 adapter.
- `core/project.py`: dependency validation, cycle rejection, atomic edits, and
  transitive invalidation. Evaluation recomputes invalidated results on demand;
  unaffected results remain cached. Prior definitions and transformations remain
  available in `history` and `transformations`.
- `adapters/`: SymPy translation in a spawned worker with a default ten-second
  wall timeout and exception isolation. Calls require identical contexts. A0
  evaluates only standard real arithmetic with principal branches and no extra
  assumptions. A custom universe, axiom set, domain, or branch is retained but
  returns `unevaluated`. Logarithms, noninteger powers, and symbolic reciprocals
  also remain unevaluated because A0 has no domain-obligation solver. This avoids
  erasing poles (`x/x`) or silently choosing complex branches. Custom products
  never become ordinary multiplication.
- `storage/`: versioned JSON with ASTs, operator definitions, semantic contexts,
  stable IDs, original definitions, edit history, and backend provenance. Loading
  checks schema, bindings, arities, graph edges, cycles, and builtin identities.
  Saved results remain historical records; current caches are recomputed rather
  than trusted as certificates. Unknown schema versions are rejected.

`project.evaluate(name)` returns IR plus an `exact` or `unevaluated` label and
provenance (source/dependency revisions, method, backend version, full context).
An exact result is an exact symbolic computation under the stated context, **not
an independently checked theorem**. Unsupported results, backend exceptions,
unrepresentable backend outputs, and timeouts retain the original expression.
`keep_unevaluated=True` bypasses evaluation. Unevaluated results are not cached,
so a later evaluation can retry. Source definitions are never replaced by results.
The `to_sympy` inspection helper requires an exact licensed representation.
JSON files are research records, not trusted proof certificates.
A saved example project is included at `examples/composition.json`.

## Scope and limitations

Tests cover workbench HTTP startup, local assets, project save/open, numeric
precision, adaptive refinement, scale domains, factorial conventions, dependency
updates through the UI session, and semantic isolation. A0 tests cover the exact integral and derivative, dependency updates, binding
capture, atomic cycle/arity rejection, semantic incompatibilities, custom operator
isolation, timeout preservation, and save/load. These checks establish the A0
vertical slice; they do not certify arbitrary integrations or custom mathematics.

Deferred to A2–A5: indexed folds,
fractional calculus/iteration, advanced geometry, analytic continuation,
transformation discovery, and axiom/model/proof engines. General free symbols,
parameterized domain proofs, matrices, recurrences, forward references, and
arbitrary user-supplied executable evaluators are not supported yet. Contexts
outside the conservative real subset can be stored and composed formally.
The worker timeout isolates slow computations; it is not a memory or security
sandbox. JSON persistence has no autosave or undo UI; history is retained for
future tooling. Dependency installation uses compatible version ranges; saved
provenance records the actual SymPy version, rather than promising identical
results across all future library versions.
