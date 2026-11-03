"""Run: python examples/advanced_geometry.py (does not require a browser)."""
from mathsandbox import Project
from mathsandbox.adapters.complex_numeric import COMPLEX_CONTEXT
from mathsandbox.adapters.padic import RATIONAL_CONTEXT
from mathsandbox.visualization.geometry import GeometrySettings, compute_geometry
from mathsandbox.visualization.sampling import PlotSettings


def main():
    project = Project()
    project.define("f(z) = 1/(z^2+1)", COMPLEX_CONTEXT)
    view = compute_geometry(project, "f", PlotSettings(lower="-2", upper="2"),
                            GeometrySettings(geometry="complex-compare", resolution=21), "1")
    print("Complex value at 1:", view["point"]["value"], "[numerically computed]")
    print("Complex convention:", view["plot"]["conventions"]["branch"])
    print("Sphere reference infinity:", view["plot"]["infinity"])
    project.define("q(x) = x", RATIONAL_CONTEXT)
    for coordinate in ("125", "1/3", "1/25", "0"):
        view = compute_geometry(project, "q", PlotSettings(), GeometrySettings(geometry="padic-tree"), coordinate)
        data = view["plot"]
        print(f"q={coordinate}: v_5={data['valuation']}, norm={data['norm']}, unit digits={data['digits']} [exact rational data; finite prefix]")


if __name__ == "__main__":
    main()
