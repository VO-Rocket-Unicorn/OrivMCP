from oriv_mcp.schemas.flight import (
    SearchFlightsInput,
    SearchFlightsOutput,
    Flight,
)
from oriv_mcp.server.app import mcp_app


@mcp_app.tool(
    name="check_available_components",
    description="List available components ready for simulation",
)
def check_available_components() -> list[str]:
    # mock data (replace with adapter later)
    components = ["component1", "component2", "component3"]
    return components


@mcp_app.tool(
    name="show_cancelled_flights",
    description="Show cancelled flight bookings",
)
def show_cancelled_flights(input: SearchFlightsInput) -> SearchFlightsOutput:
    # mock data (replace with adapter later)
    cancelled_flights = [
        Flight(flight_number="AI101", price=5000),
        Flight(flight_number="6E202", price=4500),
    ]

    return SearchFlightsOutput(flights=cancelled_flights)
