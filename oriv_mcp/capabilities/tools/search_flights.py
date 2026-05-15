from oriv_mcp.schemas.flight import (
    SearchFlightsInput,
    SearchFlightsOutput,
    Flight,
)
from oriv_mcp.server.app import mcp_app


@mcp_app.tool(
    name="search_flights",
    description="Search for flights between origin and destination",
)
def search_flights(input: SearchFlightsInput) -> SearchFlightsOutput:
    # mock data (replace with adapter later)
    flights = [
        Flight(flight_number="AI101", price=5000),
        Flight(flight_number="6E202", price=4500),
    ]

    return SearchFlightsOutput(flights=flights)
