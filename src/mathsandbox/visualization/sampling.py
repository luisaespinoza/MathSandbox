"""Bounded adaptive sampling; refinement is heuristic, never a continuity proof."""
from dataclasses import asdict, dataclass
import math
import multiprocessing as multiprocessing
import mpmath as mp
from ..adapters.numeric import NumericEvaluator, point
from ..core.project import Project
from .scales import SCALES, transform


@dataclass(frozen=True)
class PlotSettings:
    lower: str = "-5"
    upper: str = "5"
    x_scale: str = "linear"
    y_scale: str = "linear"
    digits: int = 30
    gamma_factorial: bool = False
    max_points: int = 1000

    def validate(self):
        if type(self.digits) is not int or type(self.max_points) is not int or type(self.gamma_factorial) is not bool:
            raise ValueError("Precision/sample budget must be integers and extension choice must be boolean")
        if not isinstance(self.lower, str) or not isinstance(self.upper, str):
            raise ValueError("Bounds must be decimal strings")
        if self.x_scale not in SCALES or self.y_scale not in SCALES:
            raise ValueError("Unknown coordinate scale")
        if not 15 <= self.digits <= 100 or not 100 <= self.max_points <= 2000:
            raise ValueError("Precision or sample budget out of range")
        with mp.workdps(self.digits):
            a, b = mp.mpf(self.lower), mp.mpf(self.upper)
            if not mp.isfinite(a) or not mp.isfinite(b) or not a < b:
                raise ValueError("Bounds must be finite and lower < upper")
            left, right = float(transform(a, self.x_scale)), float(transform(b, self.x_scale))
            if not math.isfinite(left) or not math.isfinite(right):
                raise ValueError("Bounds overflow display coordinates; choose a different scale")
            if not left < right:
                raise ValueError("Bounds cannot be separated in floating-point display coordinates")


def sample(project: Project, name: str, settings: PlotSettings) -> dict:
    settings.validate()
    evaluator = NumericEvaluator(project, name, gamma_factorial=settings.gamma_factorial)
    samples = {}
    warnings = set()
    budget_hit = False
    unresolved = []
    with mp.workdps(settings.digits):
        lower, upper = mp.mpf(settings.lower), mp.mpf(settings.upper)

        def evaluate(x):
            if x in samples:
                return samples[x]
            try:
                raw = evaluator.at(x)
                tx, ty = float(transform(x, settings.x_scale)), float(transform(raw, settings.y_scale))
                if not math.isfinite(tx) or not math.isfinite(ty):
                    raise ValueError("Display overflow; try log or symlog coordinates")
                row = {"x": tx, "y": ty, "raw_x": mp.nstr(x, settings.digits), "raw_y": mp.nstr(raw, settings.digits)}
                if abs(raw) > mp.mpf("1e6") and settings.y_scale == "linear":
                    warnings.add("Large magnitudes: consider log, symlog, or factorial coordinates.")
                if raw != 0 and float(raw) == 0 and settings.y_scale == "linear":
                    warnings.add("Values underflow ordinary float display; consider log coordinates.")
            except (ValueError, ZeroDivisionError, OverflowError) as error:
                warnings.add(str(error))
                row = {"x": float(transform(x, settings.x_scale)), "y": None, "raw_x": mp.nstr(x, settings.digits), "raw_y": "undefined or outside selected view"}
            samples[x] = row
            return row

        def refine(a, b, depth=0):
            nonlocal budget_hit
            if len(samples) >= settings.max_points - 1:
                budget_hit = True
                unresolved.append((a, b))
                return
            mid = (a+b)/2
            left, middle, right = evaluate(a), evaluate(mid), evaluate(b)
            ys = [r["y"] for r in (left, middle, right)]
            if right["x"] == left["x"]:
                middle["y"] = None
                warnings.add("Display precision exhausted; curve segments separated. Narrow or shift the view.")
                return
            broken = any(y is None for y in ys)
            if broken:
                curved = not all(y is None for y in ys)
            else:
                fraction = (middle["x"]-left["x"])/(right["x"]-left["x"])
                predicted = ys[0] + fraction*(ys[2]-ys[0])
                curved = abs(ys[1]-predicted) > 0.005*(1+abs(ys[1]))
            if curved and depth < 8:
                refine(a, mid, depth+1)
                refine(mid, b, depth+1)
            elif curved:
                # Break unresolved intervals rather than drawing a speculative bridge.
                middle["y"] = None
                warnings.add("Unresolved steep change or boundary: curve segments separated.")

        grid = [lower+(upper-lower)*i/64 for i in range(65)]
        for x in grid:
            evaluate(x)
        for a, b in zip(grid, grid[1:]):
            refine(a, b)
        if budget_hit:
            warnings.add("Sample budget reached; unresolved curve segments separated. Narrow the interval.")
            # Suppress only unfinished intervals; retain resolved parts of the plot.
            for a, b in unresolved:
                middle = (a+b)/2
                for x, row in samples.items():
                    if a < x < b:
                        row["y"] = None
                samples[middle] = {"x": float(transform(middle, settings.x_scale)), "y": None,
                                   "raw_x": mp.nstr(middle, settings.digits), "raw_y": "unresolved sample interval"}
        rows = [samples[x] for x in sorted(samples)]
    obj = evaluator.obj
    return {"samples": rows, "warnings": sorted(warnings), "status": "numerically-sampled",
            "error_estimate": "Heuristic refinement; no certified global error or continuity guarantee",
            "backend": "mpmath", "backend_version": mp.__version__, "source_id": obj.id,
            "source_revision": obj.revision, "context": asdict(obj.context),
            "dependency_revisions": sorted((i, project.objects[i].revision) for i in project.closure(obj.id)),
            "settings": asdict(settings)}


def _worker(writer, project, name, settings, coordinate):
    try:
        plot = sample(project, name, settings)
        value = None
        if coordinate:
            try:
                value = asdict(point(project, name, coordinate, settings.digits,
                                     gamma_factorial=settings.gamma_factorial))
            except (ValueError, ZeroDivisionError, OverflowError) as error:
                value = {"status": "undefined", "message": str(error) or "Undefined at this coordinate"}
        writer.send({"plot": plot, "point": value})
    except Exception as error:
        writer.send({"error": str(error)})
    finally:
        writer.close()


def compute(project, name, settings, coordinate="", timeout=15):
    runtime = multiprocessing.get_context("spawn")
    reader, writer = runtime.Pipe(duplex=False)
    process = runtime.Process(target=_worker, args=(writer, project, name, settings, coordinate))
    process.start()
    writer.close()
    try:
        if not reader.poll(timeout):
            raise ValueError("Plot timed out; narrow the interval or simplify the definition")
        try:
            result = reader.recv()
        except EOFError:
            raise ValueError("Numerical worker exited without a result") from None
        if "error" in result:
            raise ValueError(result["error"])
        return result
    finally:
        reader.close()
        if process.is_alive():
            process.terminate()
        process.join()
