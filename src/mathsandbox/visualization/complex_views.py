"""Finite complex samples and view-only color/sphere maps."""
import colorsys
from dataclasses import asdict
import math
import mpmath as mp
from ..adapters.complex_numeric import ComplexEvaluator


def sphere(value):
    """Inverse stereographic projection; None denotes the added infinity point."""
    if value is None:
        return [0.0, 0.0, 1.0]
    value = mp.mpc(value)
    if not mp.isfinite(value):
        raise ValueError("Only finite values or the explicit infinity reference can be projected")
    denominator = 1+abs(value)**2
    return [float(2*mp.re(value)/denominator), float(2*mp.im(value)/denominator),
            float((abs(value)**2-1)/denominator)]


def color(value):
    magnitude = abs(value)
    brightness = float(magnitude/(1+magnitude))
    hue = float((mp.arg(value)+mp.pi)/(2*mp.pi)) % 1 if magnitude else 0
    rgb = colorsys.hsv_to_rgb(hue, 0.85, brightness)
    return [round(255*c) for c in rgb]+[255]


def sample_complex(project, name, settings, geometry, coordinate=""):
    evaluator = ComplexEvaluator(project, name, gamma_factorial=settings.gamma_factorial)
    warnings = set()
    with mp.workdps(settings.digits):
        n = geometry.resolution
        xs = [mp.mpf(settings.lower)+(mp.mpf(settings.upper)-mp.mpf(settings.lower))*i/(n-1) for i in range(n)]
        ys = [mp.mpf(geometry.imaginary_lower)+(mp.mpf(geometry.imaginary_upper)-mp.mpf(geometry.imaginary_lower))*i/(n-1) for i in range(n)]
        cells = []
        for y in ys:
            row = []
            for x in xs:
                try:
                    value = evaluator.at(mp.mpc(x, y))
                    magnitude = abs(value)
                    height = mp.log1p(magnitude) if geometry.height_scale == "log1p" else magnitude
                    height_float = float(height)
                    if height != 0 and height_float == 0:
                        warnings.add("Display precision underflows small magnitudes; hover retains the high-precision value.")
                    if not math.isfinite(height_float):
                        height_float = None
                        warnings.add("Magnitude overflows the surface display; select log1p height. Other views retain finite values.")
                    row.append({"value": mp.nstr(value, settings.digits), "input": mp.nstr(mp.mpc(x, y), settings.digits),
                                "magnitude": mp.nstr(magnitude, settings.digits), "height": height_float,
                                "phase": float(mp.arg(value)) if value else None, "color": color(value),
                                "sphere": sphere(value), "branches": list(evaluator.branches), "masked": evaluator.on_cut})
                    if evaluator.on_cut:
                        warnings.add("Principal branch cuts/branch points masked in plots; no sheet continuation is inferred.")
                except (ValueError, ZeroDivisionError, OverflowError) as error:
                    warnings.add(str(error) or "Undefined complex sample omitted")
                    row.append(None)
            cells.append(row)
        # A branch phase wrap between neighboring samples indicates a cut crossing.
        # Mask both endpoints so a surface cannot bridge different principal sides.
        for j in range(n):
            for i in range(n):
                a = cells[j][i]
                if a is None:
                    continue
                for jj, ii in ((j+1, i), (j, i+1)):
                    if jj >= n or ii >= n or cells[jj][ii] is None:
                        continue
                    b = cells[jj][ii]
                    if len(a["branches"]) != len(b["branches"]) or any(
                        u is not None and v is not None and abs(u-v) > math.pi
                        for u, v in zip(a["branches"], b["branches"])):
                        a["masked"] = b["masked"] = True
                        warnings.add("Cut-crossing neighbors masked; coarse sampling is not a continuity certificate.")
        images, heights, phases, hover, projected = [], [], [], [], []
        for row in cells:
            images.append([c["color"] if c and not c["masked"] else [0, 0, 0, 0] for c in row])
            heights.append([c["height"] if c and not c["masked"] else None for c in row])
            phases.append([c["phase"] if c and not c["masked"] else None for c in row])
            hover.append([[c["input"], c["value"], c["magnitude"]] if c else ["excluded", "undefined", "undefined"] for c in row])
            projected.extend({"xyz": c["sphere"], "phase": c["phase"], "input": c["input"], "value": c["value"]}
                             for c in row if c and not c["masked"])
        point = None
        if coordinate:
            try:
                z = mp.mpc(mp.mpf(coordinate), mp.mpf(geometry.imag_coordinate))
                value = evaluator.at(z)
                point = {"status": "numerically-computed", "value": mp.nstr(value, settings.digits), "digits": settings.digits,
                         "error_estimate": "not certified", "input": mp.nstr(z, settings.digits),
                         "branch_warning": "Principal-cut boundary/branch-point value; plots are masked here." if evaluator.on_cut else ""}
            except (ValueError, ZeroDivisionError, OverflowError) as error:
                point = {"status": "undefined", "message": str(error) or "Undefined complex sample"}
    obj = evaluator.obj
    return {"plot": {"kind": "complex", "status": "numerically-sampled", "x": [float(x) for x in xs],
                     "y": [float(y) for y in ys],
                     "phase_colorscale": [[i/6, "rgb("+",".join(str(round(255*c)) for c in colorsys.hsv_to_rgb(i/6,1,1))+")"] for i in range(7)],
                     "rgba": images, "height": heights, "phase": phases,
                     "hover": hover, "sphere": projected, "infinity": sphere(None), "warnings": sorted(warnings),
                     "backend": "mpmath", "backend_version": mp.__version__, "context": asdict(obj.context),
                     "source_id": obj.id, "source_revision": obj.revision,
                     "dependency_revisions": sorted((i, project.objects[i].revision) for i in project.closure(obj.id)),
                     "settings": {**asdict(settings), **asdict(geometry)},
                     "error_estimate": "Finite grid; no certified error, continuity, singularity classification, or analytic continuation",
                     "conventions": {"color": "phase hue; brightness |w|/(1+|w|); zero black, excluded pixels transparent",
                                     "branch": "principal; cut points and phase-wrap neighbors masked",
                                     "sphere": "inverse stereographic projection of f(z); north marker is the reference infinity point, not a detected pole",
                                     "height": geometry.height_scale}}, "point": point}
