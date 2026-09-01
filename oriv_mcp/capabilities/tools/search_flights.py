from oriv_mcp.schemas.flight import Flight, SearchFlightsOutput
from oriv_mcp.server.app import mcp_app


@mcp_app.tool(
    name="search_flights",
    description="Search flights between two airports on a given date",
)
def search_flights(origin: str, destination: str, date: str) -> SearchFlightsOutput:
    # mock data (replace with adapter later)
    return SearchFlightsOutput(
        flights=[
            Flight(flight_number=f"{origin}{destination}101", price=149.00),
            Flight(flight_number=f"{origin}{destination}205", price=232.50),
        ]
    )
