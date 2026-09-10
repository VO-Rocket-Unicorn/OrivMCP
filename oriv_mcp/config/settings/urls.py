from pydantic import Field, computed_field

from oriv_mcp.config.settings.base import EnvSettings

DEFAULT_DEVICE_CLASSES_PATH = "/api/v1/device-classes"
DEFAULT_PROJECTS_PATH = "/api/v1/projects"
DEFAULT_REQUIREMENTS_PATH = "/requirements"
DEFAULT_ANCESTORS_PATH = "/ancestors"
DEFAULT_SEARCH_PATH = "/search"
DEFAULT_HEALTH_PATH = "/health"
DEFAULT_DECISION_TREES_PATH = "/api/v1/decision-trees"
DEFAULT_TAXONOMIES_PATH = "/api/v1/taxonomies"
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
    odas_base_url: str = Field(
        default="",
        description=(
            "Base URL of ODAS, the backend serving the device-class endpoints. "
            "Empty until the service exists; see temp/device-class-api-spec.md."
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
        description="Path appended to odas_base_url for the device-class collection.",
    )
    search_path: str = Field(
        default=DEFAULT_SEARCH_PATH,
        description="Path appended to the device-class collection for keyword search.",
    )
    projects_path: str = Field(
        default=DEFAULT_PROJECTS_PATH,
        description="Path appended to odas_base_url for the project collection.",
    )
    requirements_path: str = Field(
        default=DEFAULT_REQUIREMENTS_PATH,
        description="Path appended to one project's URL for its requirements.",
    )
    ancestors_path: str = Field(
        default=DEFAULT_ANCESTORS_PATH,
        description="Path appended to one requirement's URL for its ancestor chain.",
    )
    odas_health_path: str = Field(
        default=DEFAULT_HEALTH_PATH,
        description=(
            "Path appended to odas_base_url for the startup reachability probe. "
            "Sits at the host root, not under the device-class collection."
        ),
    )
    decision_trees_path: str = Field(
        default=DEFAULT_DECISION_TREES_PATH,
        description="Path appended to odas_base_url for the AI decision-tree collection.",
    )
    taxonomies_path: str = Field(
        default=DEFAULT_TAXONOMIES_PATH,
        description="Path appended to odas_base_url for resolving a taxonomy leaf by architecture name.",
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
        return f"{self.odas_base_url}{self.device_classes_path}"

    @computed_field
    @property
    def device_classes_search_url(self) -> str:
        """Keyword search across the device-class tree."""
        return f"{self.device_classes_url}{self.search_path}"

    def device_class_url(self, class_id: str) -> str:
        """One class with its ancestors, children, and siblings."""
        return f"{self.device_classes_url}/{class_id}"

    # ---- architecture selection ----
    @computed_field
    @property
    def decision_trees_url(self) -> str:
        """Collection of AI decision trees, one per device class."""
        return f"{self.odas_base_url}{self.decision_trees_path}"

    @computed_field
    @property
    def taxonomies_url(self) -> str:
        """Collection used to resolve a taxonomy leaf by architecture name."""
        return f"{self.odas_base_url}{self.taxonomies_path}"

    # ---- requirements ----
    @computed_field
    @property
    def projects_url(self) -> str:
        """The project collection. Requirements hang beneath one project."""
        return f"{self.odas_base_url}{self.projects_path}"

    # ---- health ----
    @computed_field
    @property
    def odas_health_url(self) -> str:
        """Probed once at startup to confirm odas_base_url actually points at ODAS."""
        return f"{self.odas_base_url}{self.odas_health_path}"
