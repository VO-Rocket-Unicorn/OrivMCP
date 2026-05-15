from oriv_mcp.schemas.flight import InventoryInput, InventoryOutput
from oriv_mcp.server.app import mcp_app


@mcp_app.tool(
    name="flight_inventory",
    description="Get flight inventory for an airport",
)
def flight_inventory(input: InventoryInput) -> InventoryOutput:
    return InventoryOutput(
        flights=[
            f"{input.airport}-DEL",
            f"{input.airport}-MUM",
        ]
    )
