"""Declarative construction registry. Executable adapters are never loaded from JSON."""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ConstructionDefinition:
    id: str
    kind: Literal["fractional", "iteration"]
    description: str


BUILTINS = (
    ConstructionDefinition("integer", "iteration", "Finite nonnegative integer composition; no fractional extension"),
    ConstructionDefinition("builtin:rl-integral", "fractional", "Left Riemann–Liouville integral; lower endpoint zero; power functions"),
    ConstructionDefinition("builtin:rl-derivative", "fractional", "Left Riemann–Liouville derivative; lower endpoint zero; power functions"),
    ConstructionDefinition("builtin:caputo-derivative", "fractional", "Left Caputo derivative; lower endpoint zero; admissible power functions"),
    ConstructionDefinition("positive-power", "iteration", "On x>0: the chosen family F_t(x)=x^(p^t), p>0"),
    ConstructionDefinition("translation", "iteration", "On the reals: the family F_t(x)=x+c*t"),
    ConstructionDefinition("positive-scaling", "iteration", "The family F_t(x)=a^t*x, a>0"),
)


class ConstructionRegistry:
    def __init__(self):
        self.definitions: dict[str, ConstructionDefinition] = {}
        for definition in BUILTINS:
            self.register(definition)

    def register(self, definition: ConstructionDefinition):
        if not definition.id or definition.id in self.definitions:
            raise ValueError("Duplicate or empty construction identity")
        if definition.kind not in ("fractional", "iteration"):
            raise ValueError("Unknown construction kind")
        self.definitions[definition.id] = definition

    def licensed(self, identity: str, kind: str) -> bool:
        return any(d.id == identity and d.kind == kind and self.definitions.get(identity) == d for d in BUILTINS)
