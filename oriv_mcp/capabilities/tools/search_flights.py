from oriv_mcp.server.app import mcp_app
from pathlib import Path

# @mcp_app.tool(
#     name="list_available_simulations",
#     description="List available simulations ready for execution",
# )
# def list_available_simulations() -> list[str]:
#     # mock data (replace with adapter later)
#     simulations = ["MP6517", "LV88562JA-AH", "MP6652"]
#     return simulations

single_phase_bldc_motor = """
Steps to setup simulation for single phase BLDC motor:
1. Ask user for the pdf url of the motor datasheet.
2. Pass the url to the parse_datasheet tool to extract key parameters like voltage, current, speed, torque, etc.
3. Use the extracted parameters to configure the simulation environment 
"""


# @mcp_app.tool(
#     name="setup_simulation",
#     description="Setup a simulation for a particular component",
# )
# def setup_simulation(component_category: str) -> str:
#     # mock data (replace with adapter later)
#     if component_category == "single_phase_bldc_motor":
#         return single_phase_bldc_motor
#     else:
#         return "Category not found"


# @mcp_app.tool(
#     name="parse_datasheet",
#     description="Parse a datasheet and extract key parameters",
# )
# def parse_datasheet(datasheet_url: str) -> str:
#     # Chunking takes place to obtain the physics required
#     content = Path("assets/single_phase_bldc_motor.md").read_text()
#     return content


# @mcp_app.tool(
#     name="get_parameter_values",
#     description="Get values for the required parameters for the simulation by prompting an agent",
# )
# def get_parameter_values(prompt: str) -> dict:
#     # Chunking takes place to obtain the physics required
#     print("Prompt Received:", prompt)
#     return {"parameter_values": content}
