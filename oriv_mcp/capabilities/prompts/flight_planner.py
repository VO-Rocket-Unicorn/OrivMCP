from oriv_mcp.core.decorators import prompt
from oriv_mcp.schemas.flight import PlannerInput


@prompt(
    name="flight_planner",
    description="Plan how to book a flight",
    input_schema=PlannerInput,
)
def flight_planner(input: PlannerInput) -> str:
    return f"""
You are a flight booking assistant.

Goal:
{input.goal}

Steps:
1. Identify origin and destination
2. Search flights using available tools
3. Compare prices
4. Suggest best option

Return structured steps.
"""
