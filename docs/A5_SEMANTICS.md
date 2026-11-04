# A5 axiom laboratory

The browser laboratory and `mathsandbox.axioms` package support one nonempty
sort, named constants, total functions, relations, equality, inequality,
Boolean connectives and implications. Free variables are universally closed.
Templates cover semigroups, monoids, additive groups, commutative rings and
fields. All symbols have scoped identities: `star` never becomes `mul`.
A universe does not license standard SymPy transformations of its operations.

Install the optional Z3 backend:

```sh
python -m pip install -e '.[workbench,axioms,dev]'
```
 Without it the rest of the workbench runs, and
laboratory requests report backend incompatibility with installation guidance.
Z3 is MIT licensed; native wheels are platform dependent.

## Outcomes and evidence

* **witnessed-contradiction** means unrestricted first-order Z3 checking returned
  unsatisfiable. The result includes tracked axiom dependencies and a core;
  an available solver proof artifact may be truncated and is not independently
  replayed. Finite-cardinality failure cannot produce this outcome.
* **model-constructed** includes a concrete finite structure, independently
  exhaustively checked against every axiom, or an explicit interpretation over
  ordinary reals checked relative to Z3 real arithmetic. This is relative model
  evidence, not an absolute consistency certificate.
* **undetermined** means the bounded attempts found neither sufficient evidence
  nor a suitable model. Neither consistency nor inconsistency follows.
* **backend-incompatible** preserves unsupported semantics. Nonclassical logic,
  principal complex roots and multivalued complex roots are not silently
  translated to classical uninterpreted equality. The root templates preserve
  these distinctions but this backend does not solve complex branch equations.

Finite search examines sizes 1–4 with 500 ms per size. Unrestricted checks have
an 1800 ms solver budget. Workers have a 25-second outer deadline. Models show
explicit constant assignments and total tables; `u0` need not mean zero.

Queries first recheck their foundations. A witnessed contradiction blocks
ordinary theorem certification, including a request to prove a tautology.
Otherwise a finite countermodel is checked independently, or an unrestricted
refutation of the negated goal yields backend entailment. Without a witnessed
base model this is conditional entailment. Neither result is an independently
checked theorem certificate (`certified` remains false).

## The star example

Create `star-contradiction` in the lab and choose **Check foundations**. Additive
group laws, right distributivity, `0 star 1 = 1` and `0 != 1` contradict each
other: distributing `(0+0) star 1` forces `1=1+1`, hence `0=1`.
The default protected labels preserve the additive laws, both ground equations,
and distinct constants. **Find repairs** then offers removal of right
distributivity. Applying a candidate creates a fork and freshly validates a
model, preserving the original inconsistent theory for inspection.

**Real right projection** explicitly interprets `star(a,b)=b` on ordinary
additive reals. It validates associativity, left distributivity and left unit
one, while displaying counterexamples to right distributivity, commutativity
and right unit one. This alternative is not a field multiplication.

Repair search considers deletions of at most two unprotected axioms, at most
32 candidates and eight seconds, with finite fallback sizes up to three.
Its candidates are model backed. The smallest witnessed deletion count within
these bounds is not a global minimality claim. Current protected labels are
checked again when applying a repair. Imported candidate evidence is never
trusted: a new model must be constructed before retaining a fork.

Universe and axiom revisions, symbol identities, logic and branch policy,
source text, typed AST, solver versions and logical evidence survive JSON
serialization (schema 4; older schemas remain readable). Loading verifies
source/AST agreement. Historical results are evidence records, never active
proof caches. Editing foundations marks dependent results stale and rejects
stale repair application. No result from this lab enables transformations in
another universe. There is no independent proof checker, unrestricted
consistency decision procedure or automatic conjecture generator in A5.

Run `python examples/axiom_laboratory.py` for a reproducible walkthrough and a
saved project in the current directory. A recorded walkthrough is included at
`examples/axiom_laboratory.json` and opens in the workbench. The workbench requires explicit save;
autosave and general undo remain outside this milestone.
