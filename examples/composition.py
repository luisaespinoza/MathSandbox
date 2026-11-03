"""Run from the repository root: python examples/composition.py."""
from pathlib import Path
from mathsandbox import Project, load, save


def main() -> None:
    project = Project()
    for definition in (
        "f(x) = x^3",
        "g(x) = sin(x)",
        "h(x) = Integral(f(g(t)), (t, 0, x))",
        "p(x) = diff(h(x), x)",
    ):
        project.define(definition)
    for name in ("h", "p"):
        result = project.evaluate(name)
        print(f"{name}(x) = {project.to_sympy(name)} [{result.status}]")
    path = Path("/tmp/mathsandbox-composition.json")
    save(project, path)
    restored = load(path)
    restored.define("g(x) = sin(2*x)")
    print(f"After updating g: p(x) = {restored.to_sympy('p')}")
    print(f"Project saved to {path}")


if __name__ == "__main__":
    main()
