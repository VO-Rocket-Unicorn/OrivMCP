from oriv_mcp.schemas.flight import PlannerInput

from oriv_mcp.server.app import mcp_app


@mcp_app.prompt(
    name="flight_planner",
    description="Plan how to book a flight",
)
def flight_planner(input: str) -> str:
    return f"""
You are a flight booking assistant.

Goal:
{input}

Steps:
1. Identify origin and destination
2. Search flights using available tools
3. Compare prices
4. Suggest best option

Return structured steps.
"""
