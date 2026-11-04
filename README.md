# MathSandbox — A4 analytic transformations

A local browser workbench and Python library for named mathematical definitions,
exact symbolic composition, numerical exploration, and reproducible project records. The project specification is in
[docs/ALPHA_SPEC.md](docs/ALPHA_SPEC.md). This implementation includes A0–A4; A5 remains deferred.

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
toolkit, CDN, account, or external proof tool is needed. The 3D views require a
WebGL-capable browser. The math library alone
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
  Pending editor changes are applied before saving. **Open project** accepts existing A0–A4 projects. Invalid imports leave the session intact. Sample arrays
  and point values are recomputed on open rather than trusted as certificates.
  There is no autosave; save before closing or replacing the session.

The interface and plotting assets work offline after installation. Projects remain
on your computer; this is a single-session development application, not a hosted
service. Views support a single real, complex, or rational parameter in their respective adapters. A2 constructions can be inspected and sampled when their stated domains and
backend obligations are satisfied.

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
operators and unsupported contexts remain unsupported. An integral or derivative requires a licensed
exact symbolic representation before numerical sampling; there is no new numerical
integration or differentiation algorithm in A1.

## A4 series and conditional transformations

Click **Series & continuation** for exact Taylor/Laurent coefficients, Cauchy
quadrature, and overlapping-disk Taylor transport of `1/(1+z^2)` to z=2. Click
**Implicit constraint** for the regular-branch identity `y_a+x^2*y_b=0` from
`F=y^2-a*x^3+b*x=0`, conditional on y!=0. The analysis panel also offers
differentiation, factor/simplify, and custom non-destructive rewrite templates.

Typed analytic germs, assumptions, source exclusions, reconstruction information,
and analysis history are saved. Exact finite coefficients are distinguished from
truncated/numerical results. Stale records are labeled, and imported results are
recomputed rather than trusted as certificates. See
[A4 semantics and limits](docs/A4_ANALYSIS.md), or run:

```sh
python examples/analytic_transformations.py
```

Core/workbench schema version 3 loads existing version 1/2 files. A4 project files
require this release. General branch continuation and universal PDE solving are
not implemented.

## A3 complex and p-adic geometry

Use **Complex geometry** for domain coloring, a phase-colored magnitude surface,
and a Riemann-sphere comparison of the same function. Use **p-adic geometry** for
exact rational valuation/norm and finite residue trees, starting with
`v_5(125)=3`. Complex and rational contexts are selected explicitly; original
branches, definitions, and mathematical provenance are retained.

The Geometry selector switches representations. Complex views expose Re/Im bounds,
grid resolution, and linear/log magnitude height. Rational views expose prime and
unit-digit precision; enter an exact integer or `n/d`. The p-adic tree represents
ultrametric residue containment, not Euclidean scaling.

See [A3 geometry and safeguards](docs/A3_GEOMETRY.md) for branch masks, infinity and
zero conventions, exactness labels, saved settings, and limitations. Run
`python examples/advanced_geometry.py` for a browser-free demonstration.

## A2 generalized operators

The **Power towers**, **Fractional calculus**, and **Half iteration** examples are
available directly in the workbench. These constructions require explicit
association, empty-range values, calculus definitions, iteration families, and
positive-real domains where needed. The input-domain selector edits the selected
function and invalidates downstream results. Unsupported constructions remain
unevaluated with a diagnostic and their original semantics intact.

See [A2 semantics and syntax](docs/A2_SEMANTICS.md) for formulas, conventions,
resource limits, and supported versus deferred cases. Run:

```sh
python examples/generalized_operators.py
```

A2 introduced project schema version 2; version 1 A0/A1 projects still load. The
current A4 schema is version 3. Construction choices, branches, domains, source revisions,
and exact-rule provenance survive serialization.

## A0 contracts

- `core/ir.py`: frozen, typed expression records and context, separate from SymPy.
  Objects keep stable IDs, original definitions, revisions, domains, codomains,
  universe, assumptions, branch conventions, axioms, and precision.
- `core/parser.py`: a restricted Python-AST grammar, never `eval` or SymPy string
  parsing. Supports integer/rational arithmetic, `^` or `**`, unary minus, named
  function calls, sin/cos/exp/log, factorial, gamma, definite `Integral`, and first `diff`.
  Symbols must be parameters, lexically bound variables, or explicit pi/E/I
  constants (complex constants stay formal in the real-only adapter). Function
  parameters, fold indices, and integral binders have distinct identities; substitution is
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
  wall timeout and exception isolation. Calls require compatible foundations and
  established positive arguments where a callee requires them. The adapter
  evaluates standard arithmetic over real or explicitly positive-real inputs with principal branches and no extra
  assumptions. A custom universe, axiom set, unsupported domain, or branch is retained but
  returns `unevaluated`. Logarithms, noninteger powers, and symbolic reciprocals
  remain unevaluated unless the needed positivity or nonzero condition is established. This avoids
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
isolation, timeout preservation, and save/load. A2 tests cover finite towers, fold bindings, fractional boundary conditions,
iteration family identities, domain gates, resource limits, and registry/JSON
preservation. These checks establish the implemented vertical slices; they do not certify arbitrary integrations or custom mathematics.

Deferred to A5: axiom/model/proof engines. General analytic continuation and
universal transformation discovery remain outside the implemented subset. General free symbols,
parameterized domain proofs, matrices, recurrences, forward references, and
arbitrary user-supplied executable evaluators are not supported yet. Contexts
outside the conservative real subset can be stored and composed formally.
The worker timeout isolates slow computations; it is not a memory or security
sandbox. JSON persistence has no autosave or undo UI; history is retained for
future tooling. Dependency installation uses compatible version ranges; saved
provenance records the actual SymPy version, rather than promising identical
results across all future library versions.
