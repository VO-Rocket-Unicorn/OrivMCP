package config

// Default route segments. They are the contract as it stands today; each is
// overridable so a service can move an endpoint without a code change.
const (
	DefaultDeviceClassesPath = "/api/v1/device-classes"
	DefaultProjectsPath      = "/api/v1/projects"
	DefaultRequirementsPath  = "/requirements"
	DefaultAncestorsPath     = "/ancestors"
	DefaultSearchPath        = "/search"
	DefaultVendorsPath       = "/vendors"
	DefaultHealthPath        = "/health"
	DefaultDecisionTreesPath = "/api/v1/decision-trees"
	DefaultTaxonomiesPath    = "/api/v1/taxonomies"
	DefaultOtelLogsPath      = "/v1/logs"
	DefaultOtelTracesPath    = "/v1/traces"
	DefaultOtelMetricsPath   = "/v1/metrics"
)

// URLSettings holds the base URLs of everything this server talks to, and
// builds the endpoints from them.
type URLSettings struct {
	// ---- bases ----
	OtelURL     string // required
	OdasBaseURL string // empty until configured; ODAS-backed tools then report "not configured"

	// ---- route segments ----
	OtelLogsPath      string
	OtelTracesPath    string
	OtelMetricsPath   string
	DeviceClassesPath string
	SearchPath        string
	VendorsPath       string
	ProjectsPath      string
	RequirementsPath  string
	AncestorsPath     string
	OdasHealthPath    string
	DecisionTreesPath string
	TaxonomiesPath    string
}

// ---- telemetry ----

func (u URLSettings) OtelLogsURL() string    { return u.OtelURL + u.OtelLogsPath }
func (u URLSettings) OtelTracesURL() string  { return u.OtelURL + u.OtelTracesPath }
func (u URLSettings) OtelMetricsURL() string { return u.OtelURL + u.OtelMetricsPath }

// ---- device classes ----

// DeviceClassesURL browses one level of the device-class tree.
func (u URLSettings) DeviceClassesURL() string { return u.OdasBaseURL + u.DeviceClassesPath }

// DeviceClassesSearchURL is keyword search across the device-class tree.
func (u URLSettings) DeviceClassesSearchURL() string { return u.DeviceClassesURL() + u.SearchPath }

// ---- architecture selection ----

// DecisionTreesURL is the collection of AI decision trees, one per device class.
func (u URLSettings) DecisionTreesURL() string { return u.OdasBaseURL + u.DecisionTreesPath }

// TaxonomiesURL is the collection used to resolve a taxonomy leaf by architecture name.
func (u URLSettings) TaxonomiesURL() string { return u.OdasBaseURL + u.TaxonomiesPath }

// ---- requirements ----

// ProjectsURL is the project collection. Requirements hang beneath one project.
func (u URLSettings) ProjectsURL() string { return u.OdasBaseURL + u.ProjectsPath }

// ---- health ----

// OdasHealthURL is probed once at startup to confirm OdasBaseURL actually points at ODAS.
func (u URLSettings) OdasHealthURL() string { return u.OdasBaseURL + u.OdasHealthPath }
