from dataclasses import dataclass
from ..core.ir import Expr


@dataclass(frozen=True)
class TransformationDefinition:
    id: str
    operation: str
    description: str
    parameter: Expr | None = None
    pattern: Expr | None = None
    replacement: Expr | None = None


BUILTINS = (
    TransformationDefinition("builtin:differentiate", "differentiate", "Symbolic derivative; integration needs reconstruction data"),
    TransformationDefinition("builtin:factor", "factor", "Factor while retaining the original source exclusions"),
    TransformationDefinition("builtin:simplify", "simplify", "Simplify while retaining the original source exclusions"),
)


class TransformationRegistry:
    def __init__(self):
        self.definitions = {definition.id: definition for definition in BUILTINS}

    def register(self, definition):
        if not definition.id or definition.id in self.definitions:
            raise ValueError("Duplicate or empty transformation identity")
        if definition.id.startswith("builtin:") or definition.id in ("taylor","laurent","cauchy","continue","parameter-constraint"):
            raise ValueError("Reserved builtin transformation identity")
        if definition.operation == "rewrite" and any(value is None for value in (definition.parameter, definition.pattern, definition.replacement)):
            raise ValueError("A rewrite requires a parameter, pattern, and replacement")
        if definition.operation=="rewrite" and definition.parameter.kind!="symbol":
            raise ValueError("Rewrite parameter must be a symbol")
        self.definitions[definition.id] = definition
