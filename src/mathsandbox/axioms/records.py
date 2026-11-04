"""Immutable first-order records, separate from backend-specific solver objects."""
from dataclasses import dataclass
from typing import Literal, Any


@dataclass(frozen=True)
class Symbol:
    id: str
    name: str
    arity: int
    kind: Literal['constant','function','relation']
    notation: str = ''


@dataclass(frozen=True)
class Term:
    kind: Literal['variable','constant','application']
    symbol: str
    args: tuple['Term', ...] = ()


@dataclass(frozen=True)
class Formula:
    kind: Literal['eq','ne','and','or','not','implies','predicate']
    terms: tuple[Term, ...] = ()
    operands: tuple['Formula', ...] = ()
    symbol: str = ''


@dataclass(frozen=True)
class Axiom:
    id: str
    label: str
    text: str
    formula: Formula
    revision: int = 1


@dataclass(frozen=True)
class Universe:
    id: str
    name: str
    signature: tuple[Symbol, ...]
    axioms: tuple[Axiom, ...]
    source_text: str
    revision: int = 1
    logic: str = 'classical-equality'
    branch_policy: str = 'uninterpreted-algebra'
    parent_id: str | None = None
    sort: str = 'U'


@dataclass(frozen=True)
class LogicRecord:
    id: str
    operation: str
    status: str
    universe_id: str
    universe_revision: int
    fingerprint: str
    axiom_dependencies: tuple[tuple[str,int], ...]
    backend: str
    backend_version: str
    details: dict[str, Any]
