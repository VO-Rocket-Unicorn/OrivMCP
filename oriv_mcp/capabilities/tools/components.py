from pydantic import BaseModel, Field, TypeAdapter, ConfigDict

from oriv_mcp.server.app import mcp_app
from oriv_mcp.config.http_config import http_client
from oriv_mcp.config.settings import settings


# region Schemas
# Get_component_list response schema
class Component(BaseModel):
    model_config = ConfigDict(
        validate_by_alias=True,
    )

    component_id: str = Field(
        alias="_id", description="Unique identifier for the component"
    )
    name: str
    taxonomy_tags: list[str]


class ComponentWithCategory(Component):
    category: str


components_adapter = TypeAdapter(list[Component])


# Upload_datasheet response schema
class Document(BaseModel):
    documentId: str
    filehash: str


class UploadDatasheetResponse(BaseModel):
    document: Document = Field(..., description="The uploaded document details")
    partitionId: str = Field(
        ..., description="The partition ID where the document is stored"
    )
    reuse: bool = Field(
        default=False,
        description="Whether the document was reused from an existing upload",
    )


# endregion


# region Tools
@mcp_app.tool(
    name="component_list",
    description="Get a list of components available for simulation",
)
async def component_list() -> list[ComponentWithCategory]:
    url = settings.component_list_url

    response = await http_client.get(url, headers={"origin": "localhost"})
    response.raise_for_status()

    data = response.json()

    data = components_adapter.validate_python(data.get("payload", []))

    data_with_category = [
        ComponentWithCategory(
            category="bldc-single-phase-motor", **item.model_dump(by_alias=True)
        )
        for item in data
    ]

    return data_with_category


@mcp_app.tool(
    name="upload_datasheet",
    description="Upload a datasheet PDF for Component creation",
)
async def upload_datasheet(
    filename: str,
    pdf_bytes: bytes,
) -> UploadDatasheetResponse:

    url = settings.upload_datasheet_url
    files = {"file": (filename, pdf_bytes, "application/pdf")}

    response = await http_client.post(url, files=files, headers={"origin": "localhost"})
    response.raise_for_status()

    data = response.json()
    return UploadDatasheetResponse.model_validate(data.get("payload", {}))


@mcp_app.tool(
    name="create_component_from_datasheet",
    description="Create a new component by extracting information from an uploaded datasheet",
)
async def create_component_from_datasheet(
    id: str,
    hash: str,
    partition_id: str,
) -> ComponentWithCategory:

    url = settings.create_component_url

    payload = [
        {
            "id": id,
            "hash": hash,
            "partition_id": partition_id,
        }
    ]

    response = await http_client.post(
        url, json=payload, headers={"origin": "localhost"}
    )
    response.raise_for_status()

    data = response.json()
    return ComponentWithCategory.model_validate(data.get("payload", {}))


# endregion
