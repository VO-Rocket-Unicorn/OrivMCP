from oriv_mcp.core.decorators import tool
from oriv_mcp.schemas.flight import (
    SearchFlightsInput,
    SearchFlightsOutput,
    Flight,
)


@tool(
    name="search_flights",
    description="Search flights between two cities",
    input_schema=SearchFlightsInput,
    output_schema=SearchFlightsOutput,
)
def search_flights(input: SearchFlightsInput) -> SearchFlightsOutput:
    # mock data (replace with adapter later)
    flights = [
        Flight(flight_number="AI101", price=5000),
        Flight(flight_number="6E202", price=4500),
    ]

    return SearchFlightsOutput(flights=flights)
