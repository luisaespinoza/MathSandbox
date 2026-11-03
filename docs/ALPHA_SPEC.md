# Mathematical Research Sandbox — Alpha Specification

**Version:** 0.1
**Status:** Implementation brief for Codex
**Platform:** Local-first desktop application
**Primary language:** Python
**Goal:** Explore unconventional but precisely specified mathematics using existing computer algebra, numerical, proof, model-finding, and visualization libraries.

## 1. Product vision

Build a local mathematical laboratory in which users can define objects, functions, operations, indexed notation, axioms, and mathematical universes; compose them into larger constructions; investigate their formal consequences; and inspect results symbolically, numerically, and graphically.

**Foundational design principle:** **Be maximally permissive in what users may define, and maximally rigorous in what the system certifies.** Unfamiliar mathematics is welcome; unstated assumptions and unjustified conclusions are not.

The system is not intended to rewrite SymPy, SageMath, SciPy, or existing theorem provers. Its core innovation is a **typed mathematical intermediate representation (Math IR), dependency graph, semantic-aware backend translation layer, verification/provenance system, and extensible mathematical operator and visualization registries**.

Primary audiences: exploratory mathematicians, students, researchers, and people investigating generalized, fractional, complex, nonstandard, algebraic, and axiomatically modified structures.

### Alpha success criteria

- A user can define named mathematical objects and compose them, like Desmos, but preserve symbolic forms and evaluate exactly when possible.
- A user can define a custom indexed, associative power-tower operator, with clear association and boundary conventions.
- A user can explore fractional/complex-order calculus and noninteger function iteration under explicit chosen definitions.
- A user can switch graph representations and scales, including p-adic valuation/coordinate views, without changing the source mathematical object.
- A user can derive Taylor/Laurent expansions, numerically continue analytic germs, and derive parameter differential constraints.
- A user can modify axioms, detect some contradictions, find finite models/counterexamples, receive repair suggestions, and trace assumptions.
- Every backend handoff is checked against its mathematical assumptions; exact, approximate, conditional, unproved, and unevaluated results are never conflated.
- A research session can be saved, reopened, and reproduced locally.

## 2. Non-negotiable mathematical safeguards

1. **Syntax is not semantics.** A notation is accepted even if no evaluator exists; its meaning is determined by explicit conventions and mathematical universe.
2. **Backend assumptions must not leak.** Never convert a custom product `star` to ordinary multiplication if commutativity/distributivity are not licensed.
3. **Proofs are conditional on foundations.** Track universe, axioms, branch and domain assumptions, theorem dependencies, and validation status.
4. **Consistency has multiple outcomes:** witnessed contradiction, explicit model (consistency relative to the validating metatheory), undetermined, or incompatible backend translation. Absence of contradiction is *not* a consistency proof.
5. **No unqualified extrapolation.** Complex/fractional extension of an operator requires a selected definition. Integer recursion alone does not uniquely determine continuous interpolation.
6. **No false exactness.** Numerical sampling, interpolation, truncated series, or finite tests do not establish an exact identity.
7. **Preserve branch, topology and domain.** Complex roots, logarithms, continuation paths, multivalued relations, p-adic objects, and implicit curves must retain their semantics.
8. **Inconsistent foundations must block certified theorem status.** Permit editing/diagnosing such universes, but do not certify downstream theorems by explosion. Nonclassical logics, if added later, must be explicit and separate.
9. **Undoable, explainable, non-destructive operations.** Keep original definitions and transformation history.
10. **Unsolved is a valid state.** Preserve unevaluated objects instead of rejecting them or inventing closed forms.

## 3. Alpha modules and feature requirements

### 3.1 First-class mathematical objects (P0)

Support named functions, constants, symbols, matrices, sequences, relations, implicit curves, integrals, derivatives, recurrences, operators, analytic germs, and mathematical universes.

Example user input:

```text
f(x) = x^3
g(x) = sin(x)
h(x) = Integral(f(g(t)), (t, 0, x))
p(x) = diff(h(x), x)
C(x,y,a,b) = y^2 - a*x^3 + b*x
```

Expected exact evaluation:

```text
h(x) = 2/3 - cos(x) + cos(x)^3/3
p(x) = sin(x)^3
```

Requirements:

- Dependency graph: editing `g` invalidates and recomputes affected representations of `h` and `p`.
- Support exact, numerical, hybrid, and *keep unevaluated* modes.
- Distinguish definitions from evaluated representations; retaining provenance is mandatory.
- Scope/binding of symbols and dummy variables; distinguish composition from textual substitution.
- Circular dependencies flagged by default, with explicit fixed-point/recurrence nodes permitted.
- Domain, codomain, mathematical universe, parameters, assumptions, branch conventions, and precision associated with objects.
- User-defined operators must be composable and retain symbolic identity even if backend cannot evaluate them.

### 3.2 Custom indexed/binding operator system (P0)

Support a general `IndexedFold` abstraction that can specify:

- Index variable(s), finite/symbolic range or index set.
- Operand expression or indexed function.
- Binary operation and *association* (`left`, `right`, potentially other user-defined evaluation trees).
- Empty-range convention or identity, if one exists.
- Exact finite evaluator and symbolic/unevaluated representation.
- Optional extension to noninteger or complex index/height, with separately defined continuation rules.
- User-chosen Unicode/LaTeX display and parse notation; avoid ambiguity with built-ins.

**Mandatory showcase:** a generalized sigma/pi-like right-associated exponent tower:

\[
\mathsf{E}_{k=m}^{n}a_k
= a_m^{a_{m+1}^{\cdot^{\cdot^{a_n}}}}.
\]

For constant `a`, finite integer `n`, match right-associated tetration `a ↑↑ n` with an explicitly selected height-zero convention. For variable bases, preserve each term's index. For symbolic `n`, retain the unevaluated tower. Do not automatically extend the fold to fractional heights; require an iterative functional equation/Abel coordinate/other selected construction.

Use cases beyond towers: generalized sum/product, operator composition, matrix products, continued fractions, arbitrary custom binary operations.

### 3.3 Fractional and complex-order calculus (P0/P1)

Represent `D^alpha[f](x)` and `I^alpha[f](x)` for symbolic, real or complex `alpha`.

Initial backends:

- Riemann–Liouville fractional integral/derivative, with domain/boundary assumptions.
- Caputo derivative when supported and its initial-condition differences.
- Gamma-function-based identities for power functions, with admissible parameters and branch conventions.
- Symbolic preservation when no implementation applies.
- Numeric methods and arbitrary precision via `mpmath`/SciPy when appropriate.

Important reference formula (initially `Re(alpha)>0` and suitable integrability):

\[
I_{a+}^{\alpha}f(x)=\frac{1}{\Gamma(\alpha)}\int_a^x(x-t)^{\alpha-1}f(t)\,dt.
\]

Do not assume that all fractional derivative definitions agree or that arbitrary negative/complex orders are valid without analytic continuation and boundary conditions.

### 3.4 Fractional / continuous / complex iteration (P0/P1)

Represent `Iterate(f, t)(x)` for integer, real, complex or symbolic `t`, including unevaluated cases. Require explicit family semantics:

\[
F_0(x)=x,\quad F_1(x)=f(x),\quad F_{s+t}=F_s\circ F_t.
\]

Methods:

- Recognized exact families (translations, scalings, appropriate affine/power maps).
- Abel coordinates `A(f(x)) = A(x)+1`, giving `F_t=A^{-1}(A(x)+t)` where justified.
- Schröder coordinates `Phi(f(x)) = lambda Phi(x)`, giving `F_t=Phi^{-1}(lambda^t Phi(x))` under appropriate branches and invertibility.
- Numeric approximate iterations with explicit composition-law residual and tested domain.
- Record obstructions and nonuniqueness rather than silently inventing an extension.
- Connect continuous-iteration families to infinitesimal generators/ODE flows where differentiability permits.

Alpha demo: for `x>0`, `f(x)=x^2`, `F_t(x)=x^(2^t)` and `F_(1/2)∘F_(1/2)=f` exactly. Later showcase: tetration via iteration of `f(x)=a^x` under an explicitly specified continuous-iteration construction.

### 3.5 Adaptive plotting and mathematical geometry (P0/P1)

**Coordinate/scale plugins:**

| View | Alpha expectation |
|---|---|
| Linear Cartesian | Interactive 2D explicit/implicit curves |
| Log / log-log | Positive-domain magnitude scaling |
| Symmetric log | Signed quantities crossing zero |
| Factorial / inverse-gamma coordinate | Rapid combinatorial growth; define domain and branch explicitly |
| Signed log-magnitude + complex phase | Complex data |
| Polar | Angular/radial plots |
| Reciprocal coordinates | Asymptotic behavior |
| Domain coloring | Complex argument (hue) and modulus (brightness/saturation) |
| Complex 3D magnitude | `(Re z, Im z, |f(z)|)`, phase encoded by color |
| Riemann sphere | Stereographic projection of complex coordinate and infinity |
| p-adic valuation/norm | Exact rational or p-adic inputs; chosen prime `p` |
| p-adic digit/residue tree | Finite precision, nested balls, residue classes |
| Custom transform | User-defined axis mapping with explicit domain and inverse when available |

Adaptive plotting must propose rather than silently force scales; preserve a one-click toggle to ordinary axes. When magnitude is extreme, suggest log/symlog or log-gamma scaling. Do not present p-adic topology as ordinary Cartesian Euclidean scaling; offer valuation plots and hierarchical ultrametric visualizations.

Sampling requirements:

- Adaptive resolution near steep gradients, boundaries, poles and branch changes.
- Discontinuity/branch separation; do not connect unrelated components.
- Overflow/underflow warnings, high-precision fallback, explicit uncertainty indicators.
- Compare exact symbolic expression against sampled approximation where possible.
- Display multiple representations of the *same* object side by side.

### 3.6 CAS transformations, coefficient series, and analytic continuation (P1)

SymPy/SageMath-backed operations: differentiation, integration, simplifying, factoring, substituting, equation solving, normal forms, Taylor/Laurent expansions, Fourier/Laplace transforms, algebraic transformations, ODE methods, implicit and parameter differentiation.

Treat an `AnalyticGerm` as a first-class object with center, coefficient rule/list, known or estimated disk of convergence, domain, singularity/branch information and error model. Implement:

- Taylor coefficients from symbolic differentiation, coefficient recurrences, and Cauchy contour integrals when valid.
- Taylor and Laurent visualization including coefficient plots and convergence domain.
- Recurrence-based symbolic coefficient generation where possible.
- Path-based numeric analytic continuation by Taylor re-centering through overlapping convergence disks; preserve path/branch history.
- Compare with exact evaluation when available; report finite truncation error rather than claiming exact continuation.
- Distinguish Laurent expansions at isolated singularities from Puiseux/branched expansions.

Cauchy derivative relation (on valid positively oriented contour):

\[
f^{(n)}(z_0)=\frac{n!}{2\pi i}\oint_C\frac{f(\zeta)}{(\zeta-z_0)^{n+1}}d\zeta.
\]

Alpha demo: start with `1/(1+z^2)=1-z^2+z^4-...` at zero, continue via overlapping disks to `z=2`, numerically recover `1/5` and record approximation/precision.

**Parameter PDE generator:** For implicit equation `F(x,y,a,b)=0`, use implicit differentiation and elimination on regular branches, with explicit assumptions. Demo `y^2 = a*x^3-b*x` deriving `y_a + x^2*y_b=0` where `y!=0`. A parameter PDE is a necessary identity, not automatically a complete independently solvable replacement; preserve reconstruction information.

**Transformation registry:** Suggest recognized transformations, attach forward map, inverse or reconstruction if available, domains/exceptional sets, proof or numeric verification, and provenance. Include configurable user-defined transformation rules; do not claim universal transformation discovery.

### 3.7 Axiom laboratory, logical consistency and repair (P1)

- Mathematical universe object: signature (sorts/operators), axioms, logic, theorem dependencies, permitted backend semantics.
- Initial templates: semigroups, monoids, groups, rings, fields; permit custom first-order algebraic axioms.
- Contradiction search, unsatisfiable cores where tool supports them, first-order proof attempts, finite model generation and countermodel searches.
- Suggest candidate minimal changes to eliminate a *known* contradiction, preserving user-prioritized axioms where possible. Verify candidates with model search or proof obligations; never advertise an unverified repair as complete.
- Show: witnessed inconsistent / model constructed / undetermined / backend semantics incompatible.
- Recompute/revoke theorem certification when dependent axioms change.
- Conjecture workflow: generate hypothesis -> countermodel search -> theorem proof attempt -> checked proof certificate / conditional status.
- Allow inconsistent axiom sets to be inspected and repaired, but block ordinary theorem certification under classical explosion.

Alpha case study:

```text
1 ⋆ 0 = 0
0 ⋆ 1 = 1
```

These conflict with familiar field assumptions. In particular, with additive group laws, `0+0=0`, right distributivity `(a+b)⋆c=a⋆c+b⋆c`, and `0⋆1=1`, one gets `1=1+1` and hence `1=0`. A consistent alternative over ordinary additive reals is `a⋆b=b`, which is associative and left distributive, but not generally right distributive, commutative, or two-sided unital. Present this as an explicit alternative model, not as a field.

Another case study: `iota = sqrt(-iota)` with distinct principal-root versus multivalued-root semantics; reject conflating with ordinary `i^2=-1`. Preserve branch decisions and avoid assuming all square-root definitions coincide.

### 3.8 Research workspace (P0)

- Local-first project files (versioned JSON schema or JSON plus binary array assets).
- Notebook-like expression list and contextual transforms; named operator definitions and universe editor.
- Save/reopen all axioms, operators, definitions, plots, transformation history, branches, computed outcomes, assumptions and exactness labels.
- Autosave, undo/redo and forked mathematical universes.
- Side-by-side comparison, expression dependency/derivation graph.
- Export SVG/PNG, LaTeX, compatible Python, full reproducibility manifest (library versions, precision, random seed, selected branches).
- No remote account or network dependency for normal operation after installation.

## 4. Architecture and backend adapters

### 4.1 Suggested stack

- **Desktop GUI:** PySide6 (Qt) with math expression editor and dockable panels. For rapid prototype, Panel plus local browser is acceptable; keep GUI decoupled from math core.
- **Core language:** Python.
- **Symbolic backend:** SymPy first; SageMath optional for advanced algebraic geometry and p-adics.
- **Numerical backend:** NumPy, SciPy, `mpmath`.
- **Graphing:** Plotly (embedded Qt web view if used), Matplotlib; optional PyVista for 3D surfaces.
- **Constraints/models/proofs:** Z3, Prover9/Mace4 or alternative finite-model finder, optional Lean 4 for checked proofs.
- **Data model:** typed IR plus graph of dependencies and transformations; stable IDs and versioned serialization.

Research current package APIs and distribution/licensing/installation constraints before adopting a dependency. SageMath and optional proof tools should not block installation of the baseline GUI.

### 4.2 Math IR contract

Represent, at minimum:

```text
MathObject:
  id, name, kind, expression_ast
  universe_id, signature, domain, codomain
  assumptions, parameters, branch_conventions
  dependencies, original_definition
  derived_representations, provenance
  evaluation_methods, validation_status

OperatorDefinition:
  name, arity, binding_variables, notation
  signature, universe_id, semantics
  association, identity_convention
  rewrite_rules, evaluators, extensions
  proof_obligations

TransformationResult:
  source_object_ids, result_object_ids
  method, backend, backend_version
  assumptions, domains, exceptional_sets
  forward_map, inverse_or_reconstruction
  exact_or_approximate, error_estimate
  proof_or_check_reference, dependency_ids
```

Keep expression nodes lazy, typed and immutable where practical. Bind variables properly (alpha-renaming, substitution avoiding variable capture). Track universe-specific operators by identity rather than by printable symbol. Separate mathematical objects from their rendering, and AST semantics from a backend-specific expression object.

### 4.3 Adapter lifecycle

Every backend invocation must:

1. Inspect operation, mathematical domain, active axioms, type, branch and precision.
2. Decide whether translation is valid and enumerate assumptions it needs.
3. Refuse, downgrade to a clearly labeled conditional result, or request explicit user approval if semantics would change.
4. Translate into the selected backend with no silent operator substitutions.
5. Execute with resource/time limits and exception isolation.
6. Reconstruct IR result and record backend, assumptions, evaluation method and exactness.
7. Where feasible, verify via independent symbolic substitution, model check, numerical residual, or a proof checker (clearly distinguishing these strengths).

**Do not** let a library simplify an object in a way that depends on discarded axioms. Plot and numeric adapters must be careful with implicit, multivalued or p-adic domains.

## 5. UI design

Desktop workspace panels:

1. **Expressions:** Desmos-like live named object definitions, operator notation, error/assumption indicators.
2. **Viewer:** Multiple plots of same object, scales and geometries, complex/p-adic modes.
3. **Inspect/Transform:** Applicable transforms, exact/evaluated/series representations, proof conditions.
4. **Axioms:** Universe templates, user axioms, detected conflicts, alternative model/repair branches.
5. **Derivation Graph:** Source objects, transformation edges, dependence and validity indicators.
6. **Experiment Journal:** Replayable steps, observations, export and reproducibility.

Use distinct statuses such as **Verified**, **Conditional**, **Numerically computed**, **Exploratory**, **Undetermined**, **Inconsistent**, and **Unevaluated**; avoid claiming global consistency or proof from finite testing.

## 6. Milestone plan

| Milestone | Work product | Exit criterion |
|---|---|---|
| **A0 — Math core** | Parser, typed IR, universe/context, symbol bindings, dependency graph, serialization, SymPy adapter | Named composition, exact integral, automatic downstream invalidation and round-trip save/load |
| **A1 — Workbench** | Minimal local GUI, 2D plotting, precision and exact/numeric modes, log/symlog/factorial scale modes | Interactive function composition and adaptive plotting |
| **A2 — Generalized operators** | IndexedFold with right-associated tower, fractional calculus/continuous iteration registry | Correct finite towers, one fractional calculus example, exact `x^2` half-iterate |
| **A3 — Advanced geometry** | Domain coloring, complex magnitude surface, Riemann sphere projection, p-adic valuation/tree | Correct demos and explicit metadata about branches and ultrametric topology |
| **A4 — Transformations** | Taylor/Laurent, Cauchy coefficients, numeric analytic continuation, parameter PDEs, transform registry | Reproduce continuation to `z=2` and derive/check parameter PDE |
| **A5 — Axioms** | First-order algebraic axiom editor, contradiction/model search, repair suggestions, dependency-based certification | Construct alternative `star` algebra and diagnose inconsistent field assumptions |

**Implementation priority:** complete A0 semantics before building complex GUI features; build minimal vertical slices with tests, not all subsystems at once.

## 7. Alpha acceptance tests

- [ ] **Composition:** `f(x)=x^3`, `g(x)=sin(x)`, `h(x)=Integral(f(g(t)),(t,0,x))`; get exact `2/3-cos(x)+cos(x)^3/3` and derivative `sin(x)^3`.
- [ ] **Reactive dependencies:** change `g` to `sin(2*x)`; recompute `h` and plots without stale expressions.
- [ ] **Indexed power tower:** define right-associated `E[k=m..n] a_k`; evaluate heterogeneous bases and preserve symbolic bounds.
- [ ] **Fractional calculus:** derive/evaluate a fractional power-function integral with domain assumptions; retain unsupported cases unevaluated.
- [ ] **Half iteration:** over `x>0`, verify `F_t(x)=x^(2^t)` and `F_1/2(F_1/2(x))=x^2` symbolically.
- [ ] **Adaptive axes:** plot `n!` in linear/log/factorial axes; ensure axis transforms are documented and do not change underlying values.
- [ ] **Complex plots:** render phase/magnitude domain coloring and `|f(z)|` height surface with branch warnings.
- [ ] **p-adic view:** calculate `v_5(125)=3` and show residue/ball nesting for chosen precision.
- [ ] **Taylor continuation:** take germ `1/(1+z^2)` at zero; continue numerically to `z=2`; compare to `1/5`, with error/precision metadata.
- [ ] **Parameter PDE:** derive `y_a+x^2 y_b=0` from `y^2=ax^3-bx`, explicitly restricted to regular branches.
- [ ] **Axiom contradictions:** identify a real contradiction in field assumptions plus `0⋆1=1`; attach checkable axiom dependencies.
- [ ] **Axiom repair:** construct and verify alternative `a⋆b=b` under selected surviving laws.
- [ ] **Isolation:** show that custom `⋆` does not silently become conventional SymPy multiplication.
- [ ] **Round trip:** save/reopen project with objects, custom operators, assumptions, universe forks, visualizations and provenance.

## 8. Out of scope for alpha

- Universal exact ODE/PDE solver or claim of general closed-form integration.
- Universal fractional or complex iteration for arbitrary functions.
- Automated complete consistency proof for arbitrary sufficiently expressive axiom sets.
- Fully rigorous analytic continuation certificates in arbitrary singular/multisheeted domains.
- Full Riemann-surface mesh construction and general p-adic 3D geometry.
- Reinventing symbolic algebra, numerical integration, theorem proving, or plotting from scratch.
- Cloud accounts, hosting, collaboration, marketplace, production SaaS or unrelated AI features.

## 9. Instructions to Codex

1. **Start with repository assessment** (if an existing codebase is supplied); otherwise scaffold a Python package with separate `core/`, `operators/`, `adapters/`, `verification/`, `visualization/`, `ui/`, `storage/`, and `tests/` modules.
2. Implement **A0 first**, plus a minimal demonstrable vertical slice: named functions, composition, symbolic definite integration, one live plot, dependency updates, save/load.
3. Keep the parser, typed Math IR, and semantic contracts independent of the GUI and specific backend libraries.
4. Add tests alongside each mathematical operation, especially branch/domain/axiom incompatibilities.
5. Do not invent general algorithms where no known algorithm is supplied; preserve operations formally and report unsupported cases.
6. Use existing stable packages where practical, and keep difficult optional dependencies isolated behind adapters.
7. Provide a README with installation, launch, examples, test commands, backend requirements and known limitations.
8. At each milestone, report implemented vs. deferred features and include reproducible sample projects.
9. Prefer demonstrably correct mathematical behavior over cosmetic breadth. **Never claim a proof from a numeric example or consistency from an unsuccessful contradiction search.**

---

**North star:** *A sandbox where the user is free to invent mathematical foundations, and the software is responsible for preserving meaning, tracking assumptions, exploring consequences, and distinguishing rigorous results from experimental evidence.*
