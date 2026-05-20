import httpx
from pydantic import BaseModel, Field, TypeAdapter, ConfigDict

from oriv_mcp.config.constants import ComponentCategory
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


class UploadConfig(BaseModel):
    url: str = Field(
        ..., description="The URL to which the datasheet PDF should be uploaded"
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="Any additional headers required for the upload request (e.g., authentication)",
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
            category=ComponentCategory.BLDC_SINGLE_PHASE_MOTOR,
            **item.model_dump(by_alias=True),
        )
        for item in data
    ]

    return data_with_category


@mcp_app.tool(
    name="upload_datasheet_from_url",
    description="Upload a datasheet PDF for component creation. Pass a public URL to a PDF file.",
)
async def upload_datasheet_from_url(
    pdf_url: str,
) -> UploadDatasheetResponse:
    # Step 1: Fetch PDF bytes from the public URL
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/pdf,*/*",
        "Referer": pdf_url,
    }
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        fetch_response = await client.get(pdf_url, headers=headers)
        fetch_response.raise_for_status()

        content_type = fetch_response.headers.get("content-type", "")
        if "pdf" not in content_type and not pdf_url.lower().endswith(".pdf"):
            raise ValueError(
                f"URL does not appear to be a PDF (content-type: {content_type})"
            )

        pdf_bytes = fetch_response.content

    # Step 2: Derive filename from URL
    filename = pdf_url.rstrip("/").split("/")[-1]
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    # Step 3: POST PDF bytes to backend — URL stays server-side
    files = {"file": (filename, pdf_bytes, "application/pdf")}
    upload_response = await http_client.post(
        settings.upload_datasheet_url,
        files=files,
        headers={"origin": "localhost"},
    )
    upload_response.raise_for_status()

    data = upload_response.json()
    return UploadDatasheetResponse.model_validate(data.get("payload", {}))


@mcp_app.tool(
    name="create_component_from_datasheet",
    description="Create a new component by extracting information from an uploaded datasheet",
)
async def create_component_from_datasheet(
    document_id: str,
    file_hash: str,
    partition_id: str,
) -> ComponentWithCategory:

    url = settings.create_component_url

    payload = {
        "files": [
            {
                "id": document_id,
                "hash": file_hash,
                "partition_id": partition_id,
            }
        ]
    }

    response = await http_client.post(
        url, json=payload, headers={"origin": "localhost"}
    )
    response.raise_for_status()

    data = response.json()
    data = ComponentWithCategory.model_validate(data.get("payload", {}))

    data_with_category = ComponentWithCategory(
        category=ComponentCategory.BLDC_SINGLE_PHASE_MOTOR,
        **data.model_dump(by_alias=True),
    )

    return data_with_category


# endregion
