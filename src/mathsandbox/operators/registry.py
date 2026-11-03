from dataclasses import dataclass


@dataclass(frozen=True)
class OperatorDefinition:
    id: str
    name: str
    arity: int
    universe_id: str = "standard-real"
    semantics: str = "formal"
    notation: str = ""


class OperatorRegistry:
    def __init__(self) -> None:
        self.definitions: dict[str, OperatorDefinition] = {}
        for name, arity in (("add", 2), ("mul", 2), ("pow", 2), ("sin", 1), ("cos", 1), ("exp", 1), ("log", 1)):
            self.register(OperatorDefinition("builtin:" + name, name, arity, semantics="standard:" + name))

    def register(self, definition: OperatorDefinition) -> None:
        if definition.arity < 0:
            raise ValueError("Operator arity must be nonnegative")
        if definition.id in self.definitions or any(d.name == definition.name for d in self.definitions.values()):
            raise ValueError("Duplicate operator identity or name")
        if definition.id.startswith("builtin:") and definition.semantics != "standard:" + definition.name:
            raise ValueError("Reserved builtin identity")
        self.definitions[definition.id] = definition

    def named(self, name: str) -> OperatorDefinition:
        return next(d for d in self.definitions.values() if d.name == name)
