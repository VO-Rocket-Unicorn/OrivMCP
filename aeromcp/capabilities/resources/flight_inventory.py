from aeromcp.core.decorators import resource
from aeromcp.schemas.flight import InventoryInput, InventoryOutput


@resource(
    name="flight_inventory",
    description="Get available flights from an airport",
    input_schema=InventoryInput,
    output_schema=InventoryOutput,
)
def flight_inventory(input: InventoryInput) -> InventoryOutput:
    return InventoryOutput(
        flights=[
            f"{input.airport}-DEL",
            f"{input.airport}-MUM",
        ]
    )
