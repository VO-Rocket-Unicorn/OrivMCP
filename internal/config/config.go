// Package config is the application configuration, grouped by concern.
//
// Every group reads the same flat environment (and `.env` file), so grouping
// changes how config is addressed in code (settings.Server.Port) without
// renaming a single environment variable. Lookup is case-insensitive and a
// real environment variable wins over the `.env` file, as with
// pydantic-settings, which the Python implementation used.
package config

import (
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/joho/godotenv"
)

// Values shared across config groups and the server wiring.
const (
	EnvFile        = ".env"
	RootPath       = "/"
	DefaultMCPPath = "/mcp"

	logsDirectoryName = "logs"
	repoRootMarker    = "go.mod"
)

// Environment identifies the deployment environment. Values follow the
// OpenTelemetry `deployment.environment` convention.
type Environment string

const (
	EnvironmentSandbox     Environment = "sandbox"
	EnvironmentDevelopment Environment = "development"
	EnvironmentStaging     Environment = "staging"
	EnvironmentProduction  Environment = "production"
)

var environments = []Environment{
	EnvironmentSandbox, EnvironmentDevelopment, EnvironmentStaging, EnvironmentProduction,
}

// ServerSettings: how the process identifies itself, binds, and serves MCP.
type ServerSettings struct {
	ProjectName string
	Host        string
	Port        int
	// Workers is accepted for compatibility with the Python deployment's
	// environment. A Go process already schedules across every core, so it is
	// not used.
	Workers          int
	TimeoutKeepAlive int // seconds
	// MCPPath is where the streamable HTTP MCP endpoint is served. It is also
	// aliased at "/" so clients given a bare base URL still connect.
	MCPPath string
}

// AppSettings: environment the process runs in, and where it writes on disk.
type AppSettings struct {
	Environment Environment
	LogFilePath string
}

// LogLevel is DEBUG in the sandbox and INFO everywhere else.
func (a AppSettings) LogLevel() slog.Level {
	if a.Environment == EnvironmentSandbox {
		return slog.LevelDebug
	}
	return slog.LevelInfo
}

// SecuritySettings holds the transport-security allowlists for DNS-rebinding
// protection, already normalized (see NormalizeHostEntry, NormalizeOriginEntry).
type SecuritySettings struct {
	AllowedHosts   []string
	AllowedOrigins []string
}

// HTTPSettings is outbound HTTP behaviour for the services this server calls.
type HTTPSettings struct {
	TimeoutSeconds float64
	MaxConnections int
}

// Settings is the one global settings object, composed from its groups.
type Settings struct {
	Server   ServerSettings
	App      AppSettings
	Security SecuritySettings
	HTTP     HTTPSettings
	URLs     URLSettings
}

// Load reads settings from the process environment and the `.env` file in
// the working directory.
func Load() (*Settings, error) {
	dotenv, err := godotenv.Read(EnvFile)
	if err != nil && !errors.Is(err, os.ErrNotExist) {
		return nil, fmt.Errorf("reading %s: %w", EnvFile, err)
	}
	return LoadFrom(os.Environ(), dotenv)
}

// LoadFrom builds settings from environ (KEY=value pairs, which take
// precedence) and dotenv. Every invalid value is reported, not just the first.
func LoadFrom(environ []string, dotenv map[string]string) (*Settings, error) {
	r := reader{values: make(map[string]string)}
	for key, value := range dotenv {
		r.values[strings.ToLower(key)] = value
	}
	for _, pair := range environ {
		if key, value, ok := strings.Cut(pair, "="); ok {
			r.values[strings.ToLower(key)] = value
		}
	}

	s := &Settings{
		Server: ServerSettings{
			ProjectName:      r.str("PROJECT_NAME", "OrivMCP"),
			Host:             r.str("HOST", "0.0.0.0"),
			Port:             r.integer("PORT", 8000),
			Workers:          r.integer("WORKERS", 1),
			TimeoutKeepAlive: r.integer("TIMEOUT_KEEP_ALIVE", 5),
			MCPPath:          r.str("MCP_PATH", DefaultMCPPath),
		},
		App: AppSettings{
			Environment: r.environment("ENVIRONMENT", EnvironmentProduction),
			LogFilePath: r.str("LOG_FILE_PATH", filepath.Join(RepoRoot(), logsDirectoryName)),
		},
		Security: SecuritySettings{
			AllowedHosts:   normalizeAll(r.list("ALLOWED_HOSTS"), NormalizeHostEntry),
			AllowedOrigins: normalizeAll(r.list("ALLOWED_ORIGINS"), NormalizeOriginEntry),
		},
		HTTP: HTTPSettings{
			TimeoutSeconds: r.positiveFloat("HTTP_TIMEOUT_SECONDS", 10.0),
			MaxConnections: r.positiveInteger("HTTP_MAX_CONNECTIONS", 20),
		},
		URLs: URLSettings{
			OtelURL:           r.required("OTEL_URL"),
			OdasBaseURL:       r.str("ODAS_BASE_URL", ""),
			OtelLogsPath:      r.str("OTEL_LOGS_PATH", DefaultOtelLogsPath),
			OtelTracesPath:    r.str("OTEL_TRACES_PATH", DefaultOtelTracesPath),
			OtelMetricsPath:   r.str("OTEL_METRICS_PATH", DefaultOtelMetricsPath),
			DeviceClassesPath: r.str("DEVICE_CLASSES_PATH", DefaultDeviceClassesPath),
			SearchPath:        r.str("SEARCH_PATH", DefaultSearchPath),
			VendorsPath:       r.str("VENDORS_PATH", DefaultVendorsPath),
			ProjectsPath:      r.str("PROJECTS_PATH", DefaultProjectsPath),
			RequirementsPath:  r.str("REQUIREMENTS_PATH", DefaultRequirementsPath),
			AncestorsPath:     r.str("ANCESTORS_PATH", DefaultAncestorsPath),
			OdasHealthPath:    r.str("ODAS_HEALTH_PATH", DefaultHealthPath),
			DecisionTreesPath: r.str("DECISION_TREES_PATH", DefaultDecisionTreesPath),
			TaxonomiesPath:    r.str("TAXONOMIES_PATH", DefaultTaxonomiesPath),
		},
	}
	if err := errors.Join(r.errs...); err != nil {
		return nil, fmt.Errorf("invalid configuration:\n%w", err)
	}
	return s, nil
}

// ResolvedLogDir is where log files go: LogFilePath, resolved against the
// repo root when relative.
func (s *Settings) ResolvedLogDir() string {
	if filepath.IsAbs(s.App.LogFilePath) {
		return s.App.LogFilePath
	}
	return filepath.Join(RepoRoot(), s.App.LogFilePath)
}

// RepoRoot walks up from the working directory to the nearest directory
// holding go.mod. A deployed binary has none above it, so the working
// directory itself is the root there.
func RepoRoot() string {
	cwd, err := os.Getwd()
	if err != nil {
		return "."
	}
	for dir := cwd; ; dir = filepath.Dir(dir) {
		if _, err := os.Stat(filepath.Join(dir, repoRootMarker)); err == nil {
			return dir
		}
		if filepath.Dir(dir) == dir {
			return cwd
		}
	}
}

// reader looks values up by case-insensitive name and collects every error.
type reader struct {
	values map[string]string
	errs   []error
}

func (r *reader) lookup(name string) (string, bool) {
	value, ok := r.values[strings.ToLower(name)]
	return value, ok
}

func (r *reader) fail(name, format string, args ...any) {
	r.errs = append(r.errs, fmt.Errorf("%s: %s", name, fmt.Sprintf(format, args...)))
}

func (r *reader) str(name, fallback string) string {
	if value, ok := r.lookup(name); ok {
		return value
	}
	return fallback
}

func (r *reader) required(name string) string {
	value, ok := r.lookup(name)
	if !ok {
		r.fail(name, "field required")
	}
	return value
}

func (r *reader) integer(name string, fallback int) int {
	value, ok := r.lookup(name)
	if !ok {
		return fallback
	}
	parsed, err := strconv.Atoi(strings.TrimSpace(value))
	if err != nil {
		r.fail(name, "input should be a valid integer, got %q", value)
		return fallback
	}
	return parsed
}

func (r *reader) positiveInteger(name string, fallback int) int {
	value := r.integer(name, fallback)
	if value <= 0 {
		r.fail(name, "input should be greater than 0")
	}
	return value
}

func (r *reader) positiveFloat(name string, fallback float64) float64 {
	value := fallback
	if raw, ok := r.lookup(name); ok {
		parsed, err := strconv.ParseFloat(strings.TrimSpace(raw), 64)
		if err != nil {
			r.fail(name, "input should be a valid number, got %q", raw)
			return fallback
		}
		value = parsed
	}
	if value <= 0 {
		r.fail(name, "input should be greater than 0")
	}
	return value
}

func (r *reader) environment(name string, fallback Environment) Environment {
	value, ok := r.lookup(name)
	if !ok {
		return fallback
	}
	for _, env := range environments {
		if Environment(value) == env {
			return env
		}
	}
	r.fail(name, "input should be 'sandbox', 'development', 'staging' or 'production', got %q", value)
	return fallback
}

// list parses a JSON array of strings. A comma-separated value is an error
// rather than a guess, so a misconfigured allowlist fails at startup.
func (r *reader) list(name string) []string {
	value, ok := r.lookup(name)
	if !ok {
		return nil
	}
	var parsed []string
	if err := json.Unmarshal([]byte(value), &parsed); err != nil {
		r.fail(name, `error parsing value: list values must be JSON arrays, e.g. ["a","b"]`)
		return nil
	}
	return parsed
}
