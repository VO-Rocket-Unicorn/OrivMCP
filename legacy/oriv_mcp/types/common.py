from typing import Any, TypedDict


class SpecType(TypedDict):
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
