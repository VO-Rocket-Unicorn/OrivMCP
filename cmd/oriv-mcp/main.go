// Command oriv-mcp is the Oriv MCP server.
//
// It serves streamable HTTP by default; --transport=stdio runs it over stdio
// instead, where there are no request headers, so the ODAS-backed tools
// report their missing credential.
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/modelcontextprotocol/go-sdk/jsonrpc"
	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/capabilities"
	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/config"
	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/odas"
	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/server"
	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/telemetry"
)

// Version is the service version reported to MCP clients and telemetry.
// Release builds set it with -ldflags "-X main.Version=...".
var Version = "0.1.0"

const (
	transportHTTP  = "http"
	transportStdio = "stdio"
)

func main() {
	transport := flag.String("transport", transportHTTP, "transport to serve: http or stdio")
	flag.Parse()

	if err := run(*transport); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run(transport string) error {
	if transport != transportHTTP && transport != transportStdio {
		return fmt.Errorf("unknown transport %q: want %s or %s", transport, transportHTTP, transportStdio)
	}

	settings, err := config.Load()
	if err != nil {
		return err
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	tel, err := telemetry.New(ctx, telemetry.Options{
		ServiceName:    settings.Server.ProjectName,
		ServiceVersion: Version,
		Environment:    string(settings.App.Environment),
		LogEndpoint:    settings.URLs.OtelLogsURL(),
		TraceEndpoint:  settings.URLs.OtelTracesURL(),
		MetricEndpoint: settings.URLs.OtelMetricsURL(),
	})
	if err != nil {
		return err
	}
	defer func() {
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = tel.Shutdown(shutdownCtx)
	}()

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
		return err
	}
	defer logCloser.Close()

	httpClient := odas.NewHTTPClient(
		time.Duration(settings.HTTP.TimeoutSeconds*float64(time.Second)),
		settings.HTTP.MaxConnections,
	)
	defer httpClient.CloseIdleConnections()

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

	deps := server.Deps{Settings: settings, Logger: logger, Clients: clients, Version: Version}
	mcpServer := server.NewMCPServer(deps)

	logger.Info("Starting up the application...")
	defer logger.Info("Shutting down the application...")
	server.Preflight(ctx, logger, clients.DeviceClass)

	if transport == transportStdio {
		err := mcpServer.Run(ctx, &mcp.StdioTransport{})
		if err != nil && !errors.Is(err, context.Canceled) && !isClientHangup(err) {
			return err
		}
		return nil
	}

	err = server.ServeHTTP(ctx, deps, server.NewHTTPHandler(deps, mcpServer))
	if err != nil && !errors.Is(err, http.ErrServerClosed) {
		logger.Error("server stopped: " + err.Error())
		return err
	}
	return nil
}

// codeServerClosing is the JSON-RPC error a session ends with once its
// transport is closed.
const codeServerClosing = -32004

// isClientHangup reports whether a stdio session ended because the client
// closed stdin, which is how a stdio session normally ends.
func isClientHangup(err error) bool {
	var wireErr *jsonrpc.Error
	return errors.As(err, &wireErr) && wireErr.Code == codeServerClosing
}
