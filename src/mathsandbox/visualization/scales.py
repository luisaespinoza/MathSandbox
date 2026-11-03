"""View-only coordinates; they never rewrite a mathematical definition."""
import mpmath as mp

SCALES = ("linear", "log", "symlog", "factorial")


def transform(value, scale: str):
    if scale == "linear":
        return value
    if scale == "log":
        if value <= 0:
            raise ValueError("Log coordinates require positive values")
        return mp.log10(value)
    if scale == "symlog":
        return mp.sign(value) * mp.log10(1 + abs(value))
    if scale == "factorial":
        if value < 1:
            raise ValueError("Factorial coordinates require y >= 1")
        if value == 1:
            return mp.mpf(1)
        target = mp.log(value)
        # Select the monotone inverse Gamma(t+1) branch t >= 1 explicitly.
        return mp.findroot(lambda t: mp.loggamma(t + 1) - target,
                           (mp.mpf(1), max(mp.mpf(2), target + 2)),
                           solver="bisect", tol=mp.mpf("1e-14"), maxsteps=200)
    raise ValueError("Unknown coordinate scale")
