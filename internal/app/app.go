// Package app wires the server's runtime from its settings: telemetry, the
// application logger, the ODAS clients and the MCP server.
//
// The oriv-mcp binary and the embeddable orivmcp package build the same
// runtime here, so a server run in-process behaves exactly like the deployed
// one.
package app

import (
	"context"
	"io"
	"net/http"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/capabilities"
	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/config"
	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/odas"
	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/server"
	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/telemetry"
)

// Runtime is everything the server runs on. Close releases it.
type Runtime struct {
	Deps      server.Deps
	MCPServer *mcp.Server

	tel        *telemetry.Telemetry
	logCloser  io.Closer
	httpClient *http.Client
}

// New builds the runtime. On error, whatever was already built is released.
func New(ctx context.Context, settings *config.Settings, version string) (*Runtime, error) {
	tel, err := telemetry.New(ctx, telemetry.Options{
		ServiceName:    settings.Server.ProjectName,
		ServiceVersion: version,
		Environment:    string(settings.App.Environment),
		LogEndpoint:    settings.URLs.OtelLogsURL(),
		TraceEndpoint:  settings.URLs.OtelTracesURL(),
		MetricEndpoint: settings.URLs.OtelMetricsURL(),
	})
	if err != nil {
		return nil, err
	}

	// The sandbox logs to the console at DEBUG. Everywhere else logs at INFO
	// to a rotating file and to the collector.
	sandbox := settings.App.Environment == config.EnvironmentSandbox
	loggerOpts := telemetry.LoggerOptions{
		Name:    settings.Server.ProjectName,
		Level:   settings.App.LogLevel(),
		Console: sandbox,
	}
	if !sandbox {
		loggerOpts.FilePath = settings.ResolvedLogDir()
		loggerOpts.LoggerProvider = tel.LoggerProvider
	}
	logger, logCloser, err := telemetry.NewLogger(loggerOpts)
	if err != nil {
		shutdownTelemetry(tel)
		return nil, err
	}

	httpClient := odas.NewHTTPClient(
		time.Duration(settings.HTTP.TimeoutSeconds*float64(time.Second)),
		settings.HTTP.MaxConnections,
	)

	urls := settings.URLs
	clients := capabilities.Clients{
		DeviceClass: odas.NewDeviceClassClient(httpClient, logger, odas.DeviceClassURLs{
			CollectionURL: urls.DeviceClassesURL(),
			SearchURL:     urls.DeviceClassesSearchURL(),
			VendorsPath:   urls.VendorsPath,
			HealthURL:     urls.OdasHealthURL(),
		}),
		// Same host and same credential as the device-class client.
		ArchitectureSelection: odas.NewArchitectureSelectionClient(httpClient, logger, odas.ArchitectureSelectionURLs{
			DecisionTreesURL: urls.DecisionTreesURL(),
			TaxonomiesURL:    urls.TaxonomiesURL(),
			HealthURL:        urls.OdasHealthURL(),
		}),
		// Same host and same credential again, so the startup probe the
		// device-class client runs covers this one too.
		Requirement: odas.NewRequirementClient(httpClient, logger, odas.RequirementURLs{
			ProjectsURL:      urls.ProjectsURL(),
			RequirementsPath: urls.RequirementsPath,
			AncestorsPath:    urls.AncestorsPath,
		}),
	}

	deps := server.Deps{Settings: settings, Logger: logger, Clients: clients, Version: version}
	return &Runtime{
		Deps:       deps,
		MCPServer:  server.NewMCPServer(deps),
		tel:        tel,
		logCloser:  logCloser,
		httpClient: httpClient,
	}, nil
}

// Preflight probes ODAS once, so a bad base URL surfaces at startup and not
// on the first tool call. It is reported, never fatal.
func (r *Runtime) Preflight(ctx context.Context) {
	server.Preflight(ctx, r.Deps.Logger, r.Deps.Clients.DeviceClass)
}

// Close drops idle ODAS connections, flushes telemetry, then closes the log
// file, so records written while flushing still reach it.
//
// A failed final export is not a failure to stop: the collector may simply
// be unreachable, and the SDK has already reported it. Only the log file's
// error is returned.
func (r *Runtime) Close(ctx context.Context) error {
	r.httpClient.CloseIdleConnections()
	_ = r.tel.Shutdown(ctx)
	return r.logCloser.Close()
}

// telemetryShutdownTimeout bounds the flush on an aborted startup.
const telemetryShutdownTimeout = 5 * time.Second

func shutdownTelemetry(tel *telemetry.Telemetry) {
	ctx, cancel := context.WithTimeout(context.Background(), telemetryShutdownTimeout)
	defer cancel()
	_ = tel.Shutdown(ctx)
}
