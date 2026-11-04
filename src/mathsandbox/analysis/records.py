"""Backend-independent analysis objects; saved records are never certificates."""
from dataclasses import dataclass
from typing import Any, Literal
from ..core.ir import Expr, Provenance


@dataclass(frozen=True)
class Coefficient:
    power: int
    value: Expr


@dataclass(frozen=True)
class AnalyticGerm:
    id: str
    kind: Literal["taylor", "laurent"]
    center: Expr
    variable: Expr
    coefficients: tuple[Coefficient, ...]
    inner_radius: str
    outer_radius: str
    radius_status: str
    exclusions: tuple[str, ...]
    error_model: str
    coefficient_method: str
    provenance: Provenance


@dataclass(frozen=True)
class AnalysisRecord:
    id: str
    method: str
    status: Literal["exact-symbolic", "conditional-symbolic-identity", "numerically-computed", "exploratory", "unevaluated"]
    result: Expr | None
    assumptions: tuple[str, ...]
    exceptional_sets: tuple[str, ...]
    reconstruction: str
    details: dict[str, Any]
    provenance: Provenance
