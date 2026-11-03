"""Explicit geometry settings and isolated numerical/exact view workers."""
from dataclasses import dataclass, replace
import multiprocessing as multiprocessing
import mpmath as mp
from .sampling import compute
from .complex_views import sample_complex
from ..adapters.padic import sample_padic, check_prime

GEOMETRIES = ("real", "domain-coloring", "complex-magnitude", "riemann-sphere", "complex-compare", "padic-valuation", "padic-tree")


@dataclass(frozen=True)
class GeometrySettings:
    geometry: str = "real"
    imaginary_lower: str = "-2"
    imaginary_upper: str = "2"
    imag_coordinate: str = "0"
    resolution: int = 41
    height_scale: str = "linear"
    prime: int = 5
    padic_digits: int = 4

    def validate(self, settings):
        if self.geometry not in GEOMETRIES:
            raise ValueError("Unknown geometry")
        # Validate common precision/extension fields independently of inactive bounds/scales.
        replace(settings, lower="-5", upper="5", x_scale="linear", y_scale="linear").validate()
        if self.geometry == "real":
            settings.validate()
        elif self.geometry.startswith("padic"):
            check_prime(self.prime)
            if type(self.padic_digits) is not int or not 1 <= self.padic_digits <= 8:
                raise ValueError("p-adic precision must be 1..8 base-p digits")
        else:
            replace(settings, x_scale="linear", y_scale="linear").validate()
            if type(self.resolution) is not int or self.resolution % 2 != 1 or not 21 <= self.resolution <= 81:
                raise ValueError("Complex grid resolution must be an odd integer from 21 to 81")
            if self.height_scale not in ("linear", "log1p"):
                raise ValueError("Magnitude height must be linear or log1p")
            with mp.workdps(settings.digits):
                if not isinstance(self.imaginary_lower, str) or not isinstance(self.imaginary_upper, str):
                    raise ValueError("Imaginary bounds must be decimal strings")
                bounds = [mp.mpf(settings.lower), mp.mpf(settings.upper), mp.mpf(self.imaginary_lower), mp.mpf(self.imaginary_upper)]
                if any(not mp.isfinite(v) or abs(v) > 10_000 for v in bounds) or not bounds[2] < bounds[3]:
                    raise ValueError("Complex bounds must be finite, ordered, and within ±10000")
                if float(bounds[2]) == float(bounds[3]):
                    raise ValueError("Imaginary bounds cannot be separated at display precision")


def _worker(writer, project, name, settings, geometry, coordinate):
    try:
        if geometry.geometry.startswith("padic"):
            result = sample_padic(project, name, settings, geometry, coordinate)
        else:
            result = sample_complex(project, name, settings, geometry, coordinate)
        writer.send(result)
    except Exception as error:
        writer.send({"error": str(error) or type(error).__name__})
    finally:
        writer.close()


def compute_geometry(project, name, settings, geometry, coordinate="", timeout=20):
    geometry.validate(settings)
    if geometry.geometry == "real":
        return compute(project, name, settings, coordinate, timeout)
    runtime = multiprocessing.get_context("spawn")
    reader, writer = runtime.Pipe(duplex=False)
    process = runtime.Process(target=_worker, args=(writer, project, name, settings, geometry, coordinate))
    process.start()
    writer.close()
    try:
        if not reader.poll(timeout):
            raise ValueError("Geometry computation timed out; reduce the grid or simplify the definition")
        try:
            result = reader.recv()
        except EOFError:
            raise ValueError("Geometry worker exited without a result") from None
        if "error" in result:
            raise ValueError(result["error"])
        return result
    finally:
        reader.close()
        if process.is_alive():
            process.terminate()
        process.join()
