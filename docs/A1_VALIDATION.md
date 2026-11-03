# A1 scope and validation

A1 adds a local browser workbench, not later alpha subsystems. It uses Python's
HTTP server for the local shell, Plotly for interactive 2D charts, mpmath for
pointwise evaluation and coordinate maps, and the existing A0 SymPy adapter for
symbolic computation. No symbolic algebra is reimplemented.

## Reproduce

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[workbench,dev]'
python -m pytest -q
mathsandbox
```

1. In the initial composition example, select `h` then `p`. Inspect the exact
   integral and derivative and their context/provenance.
2. Edit `g(x) = sin(x)` to `g(x) = sin(2*x)`, then Apply. The downstream result and
   graph update. In numeric mode, `p(1)` is approximately `0.7518269446689928`.
3. Change numeric precision from 30 to 70 decimal digits and inspect the numeric
   string. This changes working precision, not the source context or a certified
   accuracy bound.
4. Try an unbound symbol or a cycle. The error is visible and the previous project
   remains intact. Select Keep unevaluated to preserve the original definition.
5. Open the factorial example. It visibly selects the Gamma extension on real
   nonnegative inputs and the inverse-Gamma vertical coordinate. Toggle linear,
   log, and factorial coordinates, then Ordinary axes. Hover retains original
   function values throughout.
6. Define `r(x) = 1/x`, use bounds -1 to 1, and inspect the gap at zero. Try
   `q(x) = log(x)` to inspect real-domain exclusions. No complex values are joined
   to a real curve.
7. Save a project, switch examples, then reopen the saved JSON. Definitions,
   contexts, revision history, symbolic provenance, selected function, precision,
   coordinate scales, bounds, and Gamma-extension choice survive. The view and
   point samples are recomputed. Reopen an A0 JSON project as well.
8. Disconnect network access after installation and reload the interface. Plotly
   assets are local; there are no external fonts, scripts, or requests.

## Limits

Plots cover a single explicit real function at a time. No implicit/multivariate,
complex, p-adic, or 3D plots are included. Sampling is a bounded heuristic and can
miss narrow or highly oscillatory features. Approximate results carry no certified
error bound. There is no autosave, delete/undo UI, proof certification, or background
multi-user service. Closing the server loses unsaved session state.

## Recorded validation

- Python 3.12, SymPy 1.14.0, mpmath 1.3.0, Plotly 6.9.0: 47 pytest tests passed.
- Chromium: actual editor interactions, invalid-input recovery, dependent numeric
  recomputation, precision changes, factorial/linear/log views, JSON download and
  file upload, narrow-screen layout, no JavaScript page errors, and no remote asset
  requests passed.
- Built a noneditable wheel, installed its workbench/development extras into a
  fresh virtual environment from a local wheelhouse, and verified dependency
  consistency, the launch command, packaged HTML, browser workflow, and HTTP
  integration. This verifies installation rather than relying only on source paths.

`examples/composition.json` remains an A0-compatible source project;
`examples/factorial.json` includes the A1 view and explicit Gamma-extension choice.
