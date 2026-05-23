from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from oriv_mcp.config import settings
from oriv_mcp.config.constants import ComponentCategory
from oriv_mcp.server.app import mcp_app
from oriv_mcp.config.http_config import http_client

# =========================================================
# Base Model
# =========================================================


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


# =========================================================
# Parameter Schema Definition
# =========================================================


class ParameterDefinition(StrictBaseModel):
    type: Literal["string", "number", "integer", "boolean"]

    required: bool = Field(
        default=False,
        description="Whether the parameter is mandatory.",
    )

    default: Optional[Any] = Field(
        default=None,
        description="Default value used when omitted.",
    )

    enum: Optional[List[Any]] = Field(
        default=None,
        description="Allowed values for enum-like parameters.",
    )

    description: Optional[str] = Field(
        default=None,
        description="Human readable parameter description.",
    )


# =========================================================
# Coordinate Schema Definition
# =========================================================


class CoordinateFieldDefinition(StrictBaseModel):
    name: str = Field(
        ...,
        description="Canonical coordinate field name.",
    )

    aliases: Optional[List[str]] = Field(
        default=None,
        description="Alternative accepted field names.",
    )

    type: Literal["string", "number", "integer", "boolean"] = Field(
        ...,
        description="Coordinate value datatype.",
    )

    required: bool = Field(
        default=True,
        description="Whether this coordinate field is required.",
    )

    description: Optional[str] = Field(
        default=None,
        description="Human readable coordinate description.",
    )


class CoordinateSchema(StrictBaseModel):
    input: List[CoordinateFieldDefinition]

    output: List[CoordinateFieldDefinition]


# =========================================================
# Runtime Coordinate Values
# =========================================================


class CoordinateValue(StrictBaseModel):
    name: str = Field(
        ...,
        description="Coordinate field name.",
    )

    value: Any = Field(
        ...,
        description="Coordinate field value.",
    )


class CoordinateSample(StrictBaseModel):
    input: List[CoordinateValue] = Field(
        ...,
        description="Input coordinate values for this timestep.",
    )

    output: List[CoordinateValue] = Field(
        ...,
        description="Output coordinate values for this timestep.",
    )


# =========================================================
# Runtime Payload
# =========================================================


class SimulationPayload(StrictBaseModel):
    category: str = Field(
        default=ComponentCategory.BLDC_SINGLE_PHASE_MOTOR,
        description="Simulation category identifier.",
        examples=[ComponentCategory.BLDC_SINGLE_PHASE_MOTOR],
    )

    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dynamic simulation parameter values.",
    )

    coordinates: List[CoordinateSample] = Field(
        default_factory=list,
        description="Ordered simulation samples.",
    )


# =========================================================
# Full Simulation Schema Definition
# =========================================================


class SimulationSchema(StrictBaseModel):
    category: str

    parameters: Dict[str, ParameterDefinition]

    coordinates: CoordinateSchema


class StartCodeGenerationResponse(StrictBaseModel):
    message: str
    component_id: str
    simulation_id: str


class SimulationExecutionStatusResponse(StrictBaseModel):
    component_id: str
    simulation_id: str
    isServiceUp: bool
    frontendSetupGuide: str


# region Tools


@mcp_app.tool(
    name="get_simulation_schema",
    description="Get the simulation schema for a given component category",
)
async def get_simulation_schema(
    category: str = ComponentCategory.BLDC_SINGLE_PHASE_MOTOR,
) -> SimulationSchema:
    url = settings.get_simulation_schema_url(category)

    response = await http_client.get(url, headers={"origin": settings.csas_origin})
    response.raise_for_status()

    data = response.json()
    return SimulationSchema.model_validate(data)


@mcp_app.tool(
    name="get_simulation_values_from_component",
    description="Get simulation parameter values and coordinate samples for a given component",
)
async def get_simulation_values_from_component() -> SimulationPayload:
    simulation_values = {
        "category": ComponentCategory.BLDC_SINGLE_PHASE_MOTOR,
        "parameters": {
            "waveform_function": "sinusoidal",
            "pole_pairs": 2,
            "drive_mode": "commutated",
            "resistance": 1.0,
            "inductance": 0.001,
            "back_emf_constant": 0.01,
            "inertia": 1e-5,
            "viscous_friction": 1e-6,
        },
        "coordinates": [
            {
                "input": [
                    {"name": "time", "value": 0.0},
                    {"name": "voltage", "value": 12.0},
                    {"name": "current", "value": 0.0},
                    {"name": "position", "value": 0.0},
                ],
                "output": [{"name": "speed", "value": 0.0}],
            },
            {
                "input": [
                    {"name": "time", "value": 0.01},
                    {"name": "voltage", "value": 12.0},
                    {"name": "current", "value": 0.45},
                    {"name": "position", "value": 0.02},
                ],
                "output": [{"name": "speed", "value": 4.5}],
            },
            {
                "input": [
                    {"name": "time", "value": 0.02},
                    {"name": "voltage", "value": 12.0},
                    {"name": "current", "value": 0.7},
                    {"name": "position", "value": 0.06},
                ],
                "output": [{"name": "speed", "value": 8.1}],
            },
        ],
    }

    return SimulationPayload.model_validate(simulation_values)


@mcp_app.tool(
    name="create_simulation_for_component",
    description="Create a new simulation for a given component and return the simulation ID",
)
async def create_simulation_for_component(
    component_id: str,
) -> str:
    url = settings.create_simulation_url(component_id)

    response = await http_client.post(url, headers={"origin": settings.csas_origin})
    response.raise_for_status()

    data = response.json()
    simulation_id = data.get("payload", {}).get("simulationId")
    return simulation_id


@mcp_app.tool(
    name="start_code_generation",
    description="Start code generation for a given simulation",
)
async def start_code_generation(
    component_id: str,
    simulation_id: str,
    category: str,
    parameters: Dict[str, Any],
    coordinates: List[CoordinateSample],
) -> StartCodeGenerationResponse:
    url = settings.start_code_generation_url(component_id, simulation_id)

    payload = {
        "category": category,
        "parameters": parameters,
        "coordinates": [sample.model_dump() for sample in coordinates],
    }

    response = await http_client.post(
        url, headers={"origin": settings.csas_origin}, json=payload
    )
    response.raise_for_status()

    return {
        "message": "Code generation started successfully",
        "component_id": component_id,
        "simulation_id": simulation_id,
    }


# NOTE: This status check will be handled within `start_simulation_execution` and polled until completion, so we don't need to expose it as a separate tool.
# @mcp_app.tool(
#     name="get_code_generation_status",
#     description="Get the current status of code generation for a given simulation",
# )
# async def get_code_generation_status(
#     component_id: str,
#     simulation_id: str,
# ) -> Dict[str, Any]:
#     url = settings.get_code_generation_status_url(component_id, simulation_id)

#     response = await http_client.post(url, headers={"origin": settings.csas_origin})
#     response.raise_for_status()

#     data = response.json()
#     return data.get("payload", {})


@mcp_app.tool(
    name="start_simulation_execution",
    description="Start execution of a simulation and return the job ID for monitoring",
)
async def start_simulation_execution(
    component_id: str,
    simulation_id: str,
) -> Dict[str, Any]:
    url = settings.start_simulation_execution_url(component_id, simulation_id)

    response = await http_client.post(
        url, headers={"origin": settings.csas_origin}, json={"action": "start"}
    )
    response.raise_for_status()

    message = "Code generation in progress. Try again in a few seconds..."

    if response.status_code == 200:
        message = "Simulation execution started successfully."

    return {
        "message": message,
        "component_id": component_id,
        "simulation_id": simulation_id,
    }


@mcp_app.tool(
    name="get_simulation_execution_status",
    description="Get the current status of simulation execution for a given simulation",
)
async def get_simulation_execution_status(
    component_id: str,
    simulation_id: str,
) -> SimulationExecutionStatusResponse:
    url = settings.get_simulation_execution_status_url(component_id, simulation_id)

    response = await http_client.post(url, headers={"origin": settings.csas_origin})
    response.raise_for_status()

    data = response.json()
    return SimulationExecutionStatusResponse.model_validate(data.get("payload", {}))


@mcp_app.tool(
    name="stop_simulation_execution",
    description="Stop execution of a running simulation",
)
async def stop_simulation_execution(
    component_id: str,
    simulation_id: str,
) -> Dict[str, Any]:
    url = settings.start_simulation_execution_url(component_id, simulation_id)

    response = await http_client.post(
        url, headers={"origin": settings.csas_origin}, json={"action": "stop"}
    )
    response.raise_for_status()

    return {
        "message": "Simulation execution stopped successfully",
        "component_id": component_id,
        "simulation_id": simulation_id,
    }


# endregion
