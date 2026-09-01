from pydantic import Field, computed_field

from oriv_mcp.config.settings.base import EnvSettings

DEFAULT_DEVICE_CLASSES_PATH = "/device-classes"
DEFAULT_SEARCH_PATH = "/search"
DEFAULT_OTEL_LOGS_PATH = "/v1/logs"
DEFAULT_OTEL_TRACES_PATH = "/v1/traces"
DEFAULT_OTEL_METRICS_PATH = "/v1/metrics"


class UrlSettings(EnvSettings):
    """Base URLs of everything this server talks to, and the endpoints built from them.

    Route segments are overridable so a service can move an endpoint without a
    code change; the defaults are the contract as it stands today.
    """

    # ---- bases ----
    otel_url: str = Field(
        ...,
        description="Endpoint URL for sending logs",
    )
    ontology_base_url: str = Field(
        default="",
        description=(
            "Base URL of the device-class / ontology API. Empty until the service "
            "exists; see temp/device-class-api-spec.md for the contract."
        ),
    )

    # ---- route segments ----
    otel_logs_path: str = Field(
        default=DEFAULT_OTEL_LOGS_PATH,
        description="Path appended to otel_url for log export.",
    )
    otel_traces_path: str = Field(
        default=DEFAULT_OTEL_TRACES_PATH,
        description="Path appended to otel_url for trace export.",
    )
    otel_metrics_path: str = Field(
        default=DEFAULT_OTEL_METRICS_PATH,
        description="Path appended to otel_url for metric export.",
    )
    device_classes_path: str = Field(
        default=DEFAULT_DEVICE_CLASSES_PATH,
        description="Path appended to ontology_base_url for the device-class collection.",
    )
    search_path: str = Field(
        default=DEFAULT_SEARCH_PATH,
        description="Path appended to the device-class collection for keyword search.",
    )

    # ---- telemetry ----
    @computed_field
    @property
    def otel_logs_url(self) -> str:
        """Otel logs url"""
        return f"{self.otel_url}{self.otel_logs_path}"

    @computed_field
    @property
    def otel_traces_url(self) -> str:
        """Otel traces url"""
        return f"{self.otel_url}{self.otel_traces_path}"

    @computed_field
    @property
    def otel_metrics_url(self) -> str:
        """Otel metrics url"""
        return f"{self.otel_url}{self.otel_metrics_path}"

    # ---- device classes ----
    @computed_field
    @property
    def device_classes_url(self) -> str:
        """Browse one level of the device-class tree."""
        return f"{self.ontology_base_url}{self.device_classes_path}"

    @computed_field
    @property
    def device_classes_search_url(self) -> str:
        """Keyword search across the device-class tree."""
        return f"{self.device_classes_url}{self.search_path}"

    def device_class_url(self, class_id: str) -> str:
        """One class with its ancestors, children, and siblings."""
        return f"{self.device_classes_url}/{class_id}"
