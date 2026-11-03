"""Run: python examples/generalized_operators.py"""
from pathlib import Path
from mathsandbox import Context, Project, save


def main():
    positive = Context(domain="PositiveReals")
    project = Project()
    project.define('heterogeneous(x) = Tower(k+1, (k, 1, 3), 1)')
    project.define('fractional(x) = FractionalIntegral(x^2, (x, 0), 1/2, "riemann-liouville")', positive)
    project.define('rl(x) = FractionalDerivative(1, (x, 0), 1/2, "riemann-liouville")', positive)
    project.define('caputo(x) = FractionalDerivative(1, (x, 0), 1/2, "caputo")', positive)
    project.define("f(x) = x^2")
    project.define('half(x) = Iterate(f, 1/2, x, "positive-power")', positive)
    project.define("twice(x) = half(half(x))", positive)
    for name in ("heterogeneous", "fractional", "rl", "caputo", "half", "twice"):
        result = project.evaluate(name)
        print(f"{name}(x) = {project.to_sympy(name)} [{result.status}]")
        print("  Context:", result.provenance.context.domain, "Rules:", result.provenance.rules)
    project.define('formal(n) = Tower(2, (k, 1, n), 1)')
    result = project.evaluate("formal")
    print("Symbolic-height tower:", result.status, "—", result.provenance.diagnostic)
    path = Path("/tmp/mathsandbox-generalized-operators.json")
    save(project, path)
    print("Saved to", path)


if __name__ == "__main__":
    main()
