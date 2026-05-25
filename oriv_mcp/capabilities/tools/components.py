import httpx
from pydantic import BaseModel, Field, TypeAdapter, ConfigDict

from oriv_mcp.config.constants import ComponentCategory
from oriv_mcp.server.app import mcp_app
from oriv_mcp.config.http_config import http_client
from oriv_mcp.config.settings import settings
from oriv_mcp.config.logger_config import logger


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


class CreateComponentFromDatasheet(BaseModel):
    component_id: str = Field(
        ..., description="The unique identifier of the created component"
    )
    category: str = Field(
        default=ComponentCategory.BLDC_SINGLE_PHASE_MOTOR,
        description="The category assigned to the created component",
    )


class ComponentCreationStatusResponse(BaseModel):
    componentId: str = Field(
        ..., description="The unique identifier of the component being created"
    )
    componentName: str = Field(
        ..., description="The name of the component being created"
    )
    completed: bool = Field(
        ..., description="Whether the component creation process is completed"
    )
    inProgress: bool = Field(
        ...,
        description="Whether the component creation process is currently in progress",
    )
    currentStep: int = Field(
        ..., description="The current step number in the component creation process"
    )
    totalSteps: int = Field(
        ..., description="The total number of steps in the component creation process"
    )
    message: str = Field(
        ..., description="A human-readable message describing the current status"
    )
    progressPercentage: int = Field(
        ...,
        description="The overall progress percentage of the component creation process",
    )


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
    try:
        response = await http_client.get(
            settings.component_list_url,
            headers={"origin": settings.csas_origin},
            timeout=10.0,
        )

        response.raise_for_status()

        payload = response.json().get("payload", [])

        data = components_adapter.validate_python(payload)

        data_with_category = [
            ComponentWithCategory(
                category=ComponentCategory.BLDC_SINGLE_PHASE_MOTOR,
                **item.model_dump(by_alias=True),
            )
            for item in data
        ]

        logger.info(
            msg="Retrieved components from backend",
            extras={"component_count": len(data_with_category)},
        )

        return data_with_category

    except Exception as e:
        logger.exception(
            msg="Failed to retrieve component list",
        )

        raise RuntimeError("Failed to retrieve component list from backend") from e


@mcp_app.tool(
    name="upload_datasheet_from_url",
    description="Upload a datasheet PDF for component creation. Pass a public URL to a PDF file.",
)
async def upload_datasheet_from_url(
    pdf_url: str,
) -> UploadDatasheetResponse:
    try:
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
            headers={"origin": settings.csas_origin},
        )
        upload_response.raise_for_status()

        data = upload_response.json()
        result = UploadDatasheetResponse.model_validate(data.get("payload", {}))

        logger.info(
            msg="Datasheet uploaded successfully",
            extras={"document_id": result.document.documentId, "reuse": result.reuse},
        )

        return result

    except Exception:
        logger.exception(
            msg="Failed to upload datasheet from URL",
        )

        raise


@mcp_app.tool(
    name="create_component_from_datasheet",
    description="Create a new component by extracting information from an uploaded datasheet",
)
async def create_component_from_datasheet(
    document_id: str,
    file_hash: str,
    partition_id: str,
) -> CreateComponentFromDatasheet:
    try:
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
            url, json=payload, headers={"origin": settings.csas_origin}
        )
        response.raise_for_status()

        data = response.json()
        result = CreateComponentFromDatasheet.model_validate(data.get("payload", {}))

        logger.info(
            msg="Component creation initiated from datasheet",
            extras={"component_id": result.component_id, "category": result.category},
        )

        return result

    except Exception:
        logger.exception(
            msg="Failed to create component from datasheet",
        )

        raise


@mcp_app.tool(
    name="check_component_creation_status",
    description="Check the status of component creation from a datasheet upload",
)
async def check_component_creation_status(
    component_id: str,
) -> ComponentCreationStatusResponse:
    try:
        url = settings.check_component_creation_status_url(component_id)

        response = await http_client.post(url, headers={"origin": settings.csas_origin})
        response.raise_for_status()

        data = response.json()
        result = ComponentCreationStatusResponse.model_validate(data.get("payload", {}))

        logger.info(
            msg="Retrieved component creation status",
            extras={
                "component_id": component_id,
                "completed": result.completed,
                "progress_percentage": result.progressPercentage,
                "current_step": result.currentStep,
                "total_steps": result.totalSteps,
            },
        )

        return result

    except Exception:
        logger.exception(
            msg="Failed to check component creation status",
        )

        raise


# endregion
