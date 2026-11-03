# A3 — advanced geometry

A3 adds complex domain coloring, phase-colored magnitude surfaces, inverse
stereographic projection to the Riemann sphere, exact rational p-adic valuation
and norm, and finite residue-tree views. Source expressions remain authoritative;
rendering never substitutes another operator or changes the source definition.

## Start and reproduce

```sh
python -m pip install -e '.[workbench,dev]'
mathsandbox
python examples/advanced_geometry.py
python -m pytest -q
```

The **Complex geometry** example selects the explicit standard-complex context
and compares three views of `f(z)=1/(z^2+1)`. `logarithm(z)=log(z)` and
`root(z)=z^(1/2)` demonstrate principal cuts. The **p-adic geometry** example uses
the exact rational identity `f(x)=x` at 125 with prime 5, showing `v_5(125)=3` and
`|125|_5=1/125`. Enter `1/3` to inspect its nontrivial unit digit prefix.

The matching projects are `examples/complex_geometry.json` and
`examples/padic_geometry.json`. Save/Open retains source contexts, geometry,
bounds, precision, grid resolution, height mapping, prime, and residue depth.

## Number contexts and backend boundaries

The input-domain selector now includes **Complex inputs/outputs** and **Exact
rational inputs/outputs**. For standard contexts, selecting either explicitly
changes the number universe and codomain and retains the prior context in edit
history. Branch conventions, axiom metadata, assumptions, and original definitions
are retained. Unsupported custom foundations do not become standard just because
the domain selector changes. Domain edits invalidate downstream representations.

Complex numerical evaluation requires the standard-complex universe, complex
input/output types, ordinary arithmetic axioms, and principal branches. Rational
views require the standard-rational universe and rational input/output types.
Named calls must have matching contexts. There is no implicit analytic extension
of a real function, and no reinterpretation of real logarithms or trigonometric
functions as p-adic functions.

The original SymPy symbolic adapter remains conservative and real-only. It retains
complex/rational-context symbolic definitions unevaluated; the independent view
adapters supply clearly labeled numerical or exact-point results. A numerical
complex result is not an exact symbolic identity. An exact rational point result
is not a certificate about every input of an arbitrary function. Keep-unevaluated
mode disables these computations as well as plotting.

## Complex views

A single bounded grid supplies all comparison views of the same source object.
Re/Im input bounds are finite and within ±10000. Resolution is an odd 21..81
samples per side; working precision is the selected 15..100 decimal digits.
Computation runs in an isolated worker with a wall timeout. Ordinary axes restores
view coordinate/height transforms and never changes the source number context.

- **Domain coloring:** hue is `(arg f(z)+pi)/(2*pi)`, with a cyclic HSV palette;
  brightness is `|f(z)|/(1+|f(z)|)` and saturation is 0.85. Zero is black and has
  undefined phase. Excluded samples are transparent. Pixel values are not blended
  across excluded samples.
- **Complex magnitude:** the surface is `(Re z, Im z, |f(z)|)` with phase color.
  Optional height `ln(1+|f(z)|)` is a view mapping, not a change to function values.
  Hover preserves the sampled complex value and original modulus. The explicit
  cyclic palette has the same hue at `-pi` and `pi`.
- **Riemann sphere:** finite values `w=f(z)` map to
  `(2 Re(w), 2 Im(w), |w|^2-1)/(1+|w|^2)`. Zero is the south pole and the added
  infinity reference is the north pole. Wireframe geometry is a reference; markers
  show finite sampled function values. The north marker does not certify that an
  omitted point is a pole. Large finite values can round near the north pole at
  display precision; they are never classified as infinity.

The adapter uses mpmath on original IR arithmetic, integer/noninteger powers,
sin, cos, exp, log, and Gamma. Noninteger powers/logarithms use principal values.
The existing factorial convention extends only nonnegative **real** arguments,
not complex factorials. Custom operators, fractional-calculus/iteration nodes,
multivalued relations, and custom universes remain unsupported in this adapter.
Resource limits reject excessively large intermediate operations.

Branch points/cuts are recorded during evaluation. Samples exactly on negative
real preimages of noninteger-power/log arguments, and endpoints of adjacent grid
edges with a principal phase wrap, are masked before surface construction. A
point evaluation on a cut can show the principal boundary value with an explicit
warning. These are conservative masks: algebraic cancellation can leave more
masked points than necessary. Integer powers do not invent cuts. Undefined values
and detected poles are omitted; `z/z` at zero is never silently canceled.

This is finite-grid sampling, not adaptive analytic continuation, singularity
classification, a continuity proof, or a certified error bound. A coarse grid can
miss narrow features or off-grid singularities. No Riemann-surface mesh or sheet
continuation is constructed. Overflow suggests log height; underflow is reported
and high-precision values remain available in hover metadata. Plotly ultimately
uses ordinary floating-point display coordinates.

## Exact rational p-adic data

Enter an integer or `n/d`; decimal/scientific float approximations are rejected.
Choose a prime `2 <= p <= 97` and 1..8 **unit** base-p digits. SymPy checks primality,
evaluates rational arithmetic and integer powers, and computes exact valuations.
There is no full p-adic arithmetic package or SageMath installation requirement.

For nonzero `q`:

```text
v = v_p(q)
|q|_p = p^(-v)
u = q / p^v
u mod p^N = numerator(u) * inverse(denominator(u), p^N) mod p^N
```

The denominator of u is invertible modulo p. The digits are those of **u**, least
significant first, not of an unnormalized fractional rational. The tree shows the
unit's selected nested residue path and its siblings; sibling subtrees are
collapsed. At unit precision N, the corresponding original ball has absolute
precision `v+N`. The rational q, valuation, and norm themselves are exact; only the
visible digit prefix is truncated. For zero, valuation is infinity, norm is zero,
and the tree shows a zero residue path without claiming a unit decomposition.

Tree positions are diagram layout for containment of ultrametric balls, not
Cartesian or Euclidean distances. The valuation chart displays finite valuations;
zero/infinite valuation is an annotation, never a numeric zero bar. Negative
valuations are valid: `v_5(1/25)=-2`, `|1/25|_5=25`. `1/3` has 5-adic unit digits
`[2,3,1,3]` at N=4.

Only rational arithmetic and bounded integer powers are evaluated. Division by
zero, irrational constants, noninteger powers, transcendental/p-adic analytic
extensions, and custom products are refused. Integer bit-size and exponent
budgets keep evaluation bounded. The view describes the canonical embedding of
Q into Q_p; it does not claim an arbitrary real function extends to Q_p.

## Persistence and scope

Core project schema remains version 2. Workbench view schema is now version 2;
view schema 1 (A0/A1/A2) imports migrate to ordinary real geometry. Settings, source context/provenance, and compact view records are saved. View
records retain backend/Python versions, source/dependency revisions, settings,
branch/embedding conventions, diagnostics, point outcomes, and exact p-adic scalar
results. They omit large image/surface arrays. Samples, colors, and residue diagrams
are recomputed on reopen, and saved records never populate an evaluated cache or
serve as proof certificates. New workbench files require the A3 release. Exactness,
backend versions, source/dependency revisions, numerical precision, branch/cut
policy, embedding, and tree conventions are available in Context & provenance.

A0–A2 real workflows remain available. A4 series/continuation/PDE tools and A5
axiom/model/proof engines are deferred. Implicit curves, full Riemann surfaces,
general p-adic objects/functions, and arbitrary topology transformations are not
included in this milestone.

## Recorded validation

- Python 3.12, SymPy 1.14.0, mpmath 1.3.0, Plotly 6.9.0: all 153 tests passed.
- Mathematical checks cover unit-sphere projection and inversion, cyclic phase
  colors, principal/shifted branch cuts, integer powers without spurious cuts,
  excluded poles, overflow handling, exact valuations and multiplicative norms,
  modular residue reconstruction, negative/zero/fractional rationals, bounded
  prime/depth settings, source-context isolation, and saved provenance integrity.
- Chromium exercised domain coloring, both 3D views, comparison layout, log height,
  exact p-adic valuations and digit trees, zero and invalid inputs, project
  download/reopen with view records, and narrow-screen layout. There were no
  JavaScript page errors or remote asset requests.
- A noneditable 0.4.0 wheel installed successfully in an isolated environment;
  dependency checks passed. All 54 A3/HTTP checks passed against that installation,
  including the packaged geometry JavaScript. The full A3 browser workflow passed
  against the installed wheel as well.
- `examples/advanced_geometry.py` ran successfully. The complex and p-adic sample
  project files round-trip with their selected mathematical contexts and views.
