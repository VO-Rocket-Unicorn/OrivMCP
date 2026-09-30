from oriv_mcp.schemas.flight import InventoryOutput
from oriv_mcp.server.app import mcp_app


@mcp_app.resource(
    uri="file://documents/{airport}",
    name="flight_inventory",
    description="Get flight inventory for an airport",
)
def flight_inventory(airport: str) -> InventoryOutput:
    return InventoryOutput(
        flights=[
            f"{airport}-DEL",
            f"{airport}-MUM",
        ]
    )
