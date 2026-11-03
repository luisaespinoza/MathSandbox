# MathSandbox — A0 math core

A local Python library for named mathematical definitions, exact symbolic
composition, and reproducible project records. The project specification is in
[docs/ALPHA_SPEC.md](docs/ALPHA_SPEC.md). This implementation stops at A0.

## Install and run

Requires Python 3.11+ and SymPy 1.13–1.x (tested with Python 3.12 and SymPy 1.14).
From this checkout:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python examples/composition.py
python -m pytest -q
```

Installation needs access to PyPI; normal use needs no network or account.
SymPy (BSD license) performs symbolic algebra and uses mpmath; pytest is only a
development dependency. No GUI, numerical stack, or external proof tool is needed.

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

## A0 contracts

- `core/ir.py`: frozen, typed expression records and context, separate from SymPy.
  Objects keep stable IDs, original definitions, revisions, domains, codomains,
  universe, assumptions, branch conventions, axioms, and precision.
- `core/parser.py`: a restricted Python-AST grammar, never `eval` or SymPy string
  parsing. Supports integer/rational arithmetic, `^` or `**`, unary minus, named
  function calls, sin/cos/exp/log, definite `Integral`, and first `diff`.
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

A0 tests cover the exact integral and derivative, dependency updates, binding
capture, atomic cycle/arity rejection, semantic incompatibilities, custom operator
isolation, timeout preservation, and save/load. These checks establish the A0
vertical slice; they do not certify arbitrary integrations or custom mathematics.

Deferred to A1–A5: GUI and plotting, numeric evaluation modes, indexed folds,
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
