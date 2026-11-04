# A4 — series, continuation, and conditional transformations

A4 adds first-class analytic germs, exact Taylor/Laurent coefficients, rational
coefficient recurrences, numerical Cauchy coefficients, bounded Taylor transport,
and a regular-branch implicit parameter-constraint generator. SymPy performs
symbolic algebra; mpmath performs numerical arithmetic and quadrature. These tools
do not replace the original definitions or certify a general theorem.

## Run and use

```sh
python -m pip install -e '.[workbench,dev]'
mathsandbox
python examples/analytic_transformations.py
python -m pytest -q
```

Click **Series & continuation** to load `f(z)=1/(1+z^2)` and `pole(z)=1/z` in the
explicit principal complex context. The initial analysis continues f from zero to
2 through overlapping disks, recovering approximately `1/5`. The analysis panel
also offers Taylor, Laurent, Cauchy coefficient quadrature, differentiation,
factoring, simplifying, and custom rewrites. Choose the source function, method,
center, truncation order, and working precision, then **Analyze selected function**.
Pending definitions are applied atomically first. Keep-unevaluated mode disables
analysis. Errors retain the source and do not add partial analysis objects.

Click **Implicit constraint** to load
`F(x,y,a,b)=y^2-a*x^3+b*x`, interpreted as F=0 only by the selected implicit-analysis
operation. Its necessary identity is `y_a + x^2*y_b = 0`, conditional on F=0 and
y!=0. The original polynomial function is retained. Ordinary one-parameter
plotting is unavailable for this four-parameter source, but the analysis panel
works independently.

The sample files are `examples/series_continuation.json` and
`examples/implicit_constraint.json`. Save/Open preserves analysis controls, typed
germs, transformation definitions, result records, source/dependency revisions,
assumptions, exclusions, and reconstruction information. Saved results can be
viewed through the historical-record list, explicitly labeled not recomputed.
Changed source/dependency revisions mark them stale. Recompute to obtain a result
for current definitions; imported results never populate an evaluated cache.

## Germs and series

`AnalyticGerm` is an immutable backend-independent record with a stable ID,
source provenance, typed center/variable/coefficient ASTs, kind, a local disk or
annulus description, source exclusions, coefficient method, and an error model.
An exact finite coefficient list is not an exact representation of the whole
function. A truncated series has no certified global remainder bound.

Analytic germs require one parameter in the standard principal complex context.
Real sources are not silently extended. The initial subset supports rational
functions and meromorphic combinations of sin/cos/exp of polynomial arguments.
Denominator/source-exclusion root isolation is limited to complete degree-four
root sets, elementary entire arguments to degree eight, and integer powers to 64.
Other operators, custom foundations, Gamma, integrals, A2 constructions, and
unlicensed named calls are refused while the original IR remains intact.

- **Taylor:** exact coefficients from SymPy series, symbolic derivatives divided
  by n!, or the rational recurrence. The order is 2..48; retained powers run from
  zero through order-1.
- **Rational recurrence:** after shifting center c, write Q(w)f(w)=P(w). Exact
  coefficients obey `Q0*a[n] = P[n] - sum(Q[k]*a[n-k], k>=1)`. This is a known
  coefficient identity implemented with SymPy polynomial arithmetic, not a new CAS.
- **Laurent:** the initial implementation supports a finite principal part and a
  local punctured annulus, with integer powers only. For `1/z`, the coefficient
  at -1 is 1. Around i, `1/(1+z^2)` has residue `-i/2` and nearest other exclusion
  at distance 2. Outer annuli and infinite principal parts are not implemented.
- **Convergence/domain view:** a conservative local source-domain radius comes
  from the nearest source exclusion. It need not be the maximal power-series
  convergence radius. Numerical radius evaluation is an estimate. Supported
  entire templates can have unbounded radius. Source holes remain excluded even
  if algebraic cancellation would give an analytic extension: `z/z` is not filled
  at zero without an explicit extension choice.

Branched/Puiseux/logarithmic germs are not mislabeled as integer Laurent series.
Essential singularities can have Laurent expansions mathematically, but their
infinite principal parts are outside this finite format. A conservative refusal
is not a claim that the mathematical expansion does not exist.

The coefficient chart uses `log10(1+|a[n]|)` for display and preserves exact
coefficients in hover/text. Local diagrams use coordinates relative to the germ
center; continuation diagrams use actual complex centers. These are views, not
changes to the source object or its coefficients.

## Cauchy coefficients

For an analytic Taylor center, a positively oriented circle of radius rho yields

```text
a[n] = 1/(2*pi*rho^n) * integral_0^(2*pi) f(c+rho*exp(i*theta))*exp(-i*n*theta) dtheta.
```

mpmath quadrature estimates up to the first eight coefficients at 15..100 working
decimal digits. The circle must be safely inside the source-exclusion radius;
source poles or holes at the center are refused. Exact symbolic coefficients are
retained alongside numerical estimates and reference differences. Quadrature
error estimates are heuristic and may omit roundoff; they are not certified
bounds. No numerical agreement is promoted to an exact identity.

## Numerical continuation

Continuation currently applies to rational functions with numerator degree <=12
and denominator degree <=4. It is **not** a generic analytic-continuation solver.

1. Recompute the exact initial germ from the source, even when continuing a germ
   loaded from JSON. Imported coefficient claims are never trusted as a seed.
2. Follow 2..32 explicit waypoints, written `real,imag; real,imag; ...`. Coordinates
   are integer/rational/finite decimal components within ±100. The path must start
   at the germ center. Segments crossing or too close to a source exclusion are
   rejected at working precision.
3. Transport by a finite Taylor polynomial. Steps are bounded by 0.3 times the
   nearest exclusion distance and by 0.5 absolute length. At most 128 overlapping
   disks are allowed.
4. Replenish coefficients from the rational differential identity
   `d(Q*f-P)/dz=0`. The new constant coefficient is **only** the transported value;
   it is not reset to exact `P(new_center)/Q(new_center)`. The differential
   invariant and retained-tail indicators are recorded at every step.
5. Repeat at order+8 and digits+10. Return the refined result, observed refinement
   difference, path, both working orders/precisions, and branch history. Compare
   against a separate direct endpoint evaluation only after transport.

Observed refinement differences and retained-tail indicators are not rigorous
error bounds. The tests perturb the seed to verify that transport carries that
perturbation instead of secretly resetting to the exact source. Rational
functions are single-valued; the recorded path does not implement logarithmic
monodromy, branch switching, or sheet continuation.

## Implicit parameter constraints

The initial generator accepts a polynomial F, a dependent variable y, and two
named parameters a,b. On a regular branch:

```text
F_y*y_a + F_a = 0
F_y*y_b + F_b = 0
```

SymPy finds a polynomial syzygy of F_a,F_b using their polynomial gcd and checks
`c_a*F_a+c_b*F_b=0`. It then yields
`c_a*y_a+c_b*y_b=0` conditional on F=0 and F_y!=0. Removing a common polynomial
factor to construct the syzygy does not divide the resulting functional identity
by that factor; no unnecessary x!=0 assumption is added in the demo.

Records retain parameter partial formulas, the checked algebraic residual,
regularity factors, original equation, derivative bindings, and reconstruction
requirements. Singular branches are excluded, identically zero F_y is refused,
and rational implicit sources with denominator issues are deferred. A necessary
parameter PDE is not a complete independently solvable replacement for F=0, nor
an existence/uniqueness theorem for the implicit function.

## Transformation registry and records

The registry supplies fixed candidates for derivative, factor, and simplify;
invocation checks their admissibility. It does not discover universal transforms.
Custom unary rewrite templates use x and are registered through the UI or
`project.register_rewrite(name, pattern, replacement)`.

Transforms are non-destructive. Verified symbolic template/output equality under
the recorded context produces an exact-symbolic result. Unproved rewrites remain
**exploratory** and are never certified equivalent. Source and output restrictions
remain attached; branch cuts are not dropped when differentiating a logarithm.
Differentiation records the need for an integration constant to reconstruct the
original. Declarative registry entries cannot install executable evaluators from
JSON.

Core and workbench schema version 3 persist these additions; existing schema 1/2
projects migrate with empty analysis collections. Old releases cannot read A4
files. Backend versions, original source definitions, dependent revisions,
assumptions, exceptional sets, branch/context metadata, exactness labels,
reconstruction, and numeric precision/path/error information survive save/load.
Analysis runs in a spawned worker with a 25-second default wall timeout. Historical
records remain untrusted mathematical records, not proof certificates.

A5 axiom/model/proof engines remain deferred. There is no general PDE solver,
universal transform discovery, arbitrary custom theorem certification, or general
multisheeted continuation in this milestone.

## Recorded validation

- Python 3.12, SymPy 1.14.0, mpmath 1.3.0, Plotly 6.9.0: all 190 tests passed.
- Tests check three exact Taylor coefficient methods, finite-principal-part
  Laurent series and complex centers, Cauchy quadrature versus symbolic values,
  continuation through overlapping disks, a perturbed-seed check against exact
  resets, singular paths, conditional parameter syzygies, source holes/cuts,
  context isolation, exact versus exploratory rewrites, stale germs, forged saved
  coefficients, detached historical records, schema migration, and worker limits.
- Chromium exercised the two examples, coefficient/disk plots, Cauchy/Laurent
  selection, singular-path refusal, the conditional PDE, custom rewrites, stale
  history, unexecuted control persistence, and save/reopen of typed records.
  Narrow-screen layout passed with no JavaScript page errors or remote assets.
- A noneditable 0.5.0 wheel installed into an isolated environment with dependency
  checks passing. All 38 A4/HTTP checks passed there, including the packaged
  analysis JavaScript. The complete A4 browser workflow also passed against it.
- The command-line example executed, and both supplied A4 JSON projects restored
  their typed germs and analysis records without changes to their definitions.
