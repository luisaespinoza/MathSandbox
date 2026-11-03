"""Immutable, backend-independent expression and semantic records."""
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4


def identity() -> str:
    return str(uuid4())


@dataclass(frozen=True)
class Context:
    universe_id: str = "standard-real"
    domain: str = "Reals"
    codomain: str = "Reals"
    assumptions: tuple[str, ...] = ()
    branches: tuple[str, ...] = ("principal",)
    axioms: tuple[str, ...] = ("standard-arithmetic",)
    precision: int = 53


@dataclass(frozen=True)
class Expr:
    kind: Literal["integer", "symbol", "operator", "call", "integral", "derivative", "constant", "fold", "fractional", "iterate"]
    value: str
    args: tuple["Expr", ...] = ()
    conventions: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class MathObject:
    id: str
    name: str
    parameters: tuple[Expr, ...]
    expression: Expr
    original_definition: str
    context: Context
    dependencies: tuple[str, ...]
    revision: int = 1
    kind: str = "function"


@dataclass(frozen=True)
class Provenance:
    source_id: str
    source_revision: int
    dependency_revisions: tuple[tuple[str, int], ...]
    method: str
    backend: str
    backend_version: str
    context: Context
    rules: tuple[str, ...] = ()
    diagnostic: str = ""


@dataclass(frozen=True)
class Representation:
    expression: Expr
    status: Literal["exact", "unevaluated"]
    provenance: Provenance
