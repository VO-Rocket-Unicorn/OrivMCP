// Package server assembles the MCP server and serves it over streamable
// HTTP or stdio.
package server

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"strconv"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/capabilities"
	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/config"
	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/odas"
)

// HealthPath answers liveness probes. It sits outside the transport guard.
const HealthPath = "/health"

// shutdownTimeout bounds how long in-flight requests get to finish.
const shutdownTimeout = 10 * time.Second

// Deps is what the server is built from.
type Deps struct {
	Settings *config.Settings
	Logger   *slog.Logger
	Clients  capabilities.Clients
	Version  string
}

// NewMCPServer builds the MCP server with every capability registered.
func NewMCPServer(deps Deps) *mcp.Server {
	server := mcp.NewServer(
		&mcp.Implementation{Name: deps.Settings.Server.ProjectName, Version: deps.Version},
		&mcp.ServerOptions{
			// Everything is registered before the first session, so the lists
			// never change, and this server sends no log notifications.
			Capabilities: &mcp.ServerCapabilities{
				Tools:     &mcp.ToolCapabilities{},
				Prompts:   &mcp.PromptCapabilities{},
				Resources: &mcp.ResourceCapabilities{},
			},
		},
	)
	tools := capabilities.Register(server, deps.Clients, deps.Logger)
	server.AddReceivingMiddleware(tracingMiddleware, unknownToolMiddleware(tools))
	return server
}

// NewHTTPHandler routes the MCP endpoint (at the configured path and at "/",
// so a client given the bare base URL still connects) and the health check.
func NewHTTPHandler(deps Deps, server *mcp.Server) http.Handler {
	streamable := mcp.NewStreamableHTTPHandler(
		func(*http.Request) *mcp.Server { return server },
		&mcp.StreamableHTTPOptions{
			Logger: deps.Logger,
			// The allowlist guard below is the DNS-rebinding protection. The
			// SDK's own localhost check would also reject a tunnel hostname
			// that the allowlist explicitly admits.
			DisableLocalhostProtection: true,
		},
	)
	guarded := transportGuard{
		allowedHosts:   deps.Settings.Security.AllowedHosts,
		allowedOrigins: deps.Settings.Security.AllowedOrigins,
		logger:         deps.Logger,
	}.wrap(streamable)

	mux := http.NewServeMux()
	mux.HandleFunc("GET "+HealthPath, func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	})
	mcpPath := deps.Settings.Server.MCPPath
	mux.Handle(mcpPath, guarded)
	if mcpPath != config.RootPath {
		// "/" is a catch-all in a ServeMux; "/{$}" matches the root exactly,
		// so every other unknown path still 404s.
		mux.Handle("/{$}", guarded)
	}
	return mux
}

// unknownToolMiddleware answers a call to a tool that does not exist with an
// error result the model can read, rather than a protocol error.
func unknownToolMiddleware(tools []string) mcp.Middleware {
	known := make(map[string]bool, len(tools))
	for _, name := range tools {
		known[name] = true
	}
	return func(next mcp.MethodHandler) mcp.MethodHandler {
		return func(ctx context.Context, method string, req mcp.Request) (mcp.Result, error) {
			if params, ok := req.GetParams().(*mcp.CallToolParamsRaw); ok && params != nil && !known[params.Name] {
				return &mcp.CallToolResult{
					Content: []mcp.Content{&mcp.TextContent{Text: "Unknown tool: " + params.Name}},
					IsError: true,
				}, nil
			}
			return next(ctx, method, req)
		}
	}
}

// Preflight probes ODAS once at startup, so a bad base URL surfaces here and
// not on the first tool call. It is reported, never fatal: ODAS may simply
// come up later.
func Preflight(ctx context.Context, logger *slog.Logger, client *odas.DeviceClassClient) {
	reachable, detail := client.CheckHealth(ctx)
	if reachable {
		logger.InfoContext(ctx, "ODAS preflight: "+detail)
		return
	}
	logger.ErrorContext(ctx, fmt.Sprintf("ODAS preflight FAILED: %s. Device-class tools will report the service "+
		"as unavailable until this is fixed.", detail))
}

// ServeHTTP serves until ctx is cancelled, then drains in-flight requests.
func ServeHTTP(ctx context.Context, deps Deps, handler http.Handler) error {
	s := deps.Settings.Server
	if s.Workers > 1 {
		deps.Logger.Warn(fmt.Sprintf("WORKERS=%d is ignored: a single Go process already uses every core", s.Workers))
	}
	httpServer := &http.Server{
		Addr:              net.JoinHostPort(s.Host, strconv.Itoa(s.Port)),
		Handler:           handler,
		IdleTimeout:       time.Duration(s.TimeoutKeepAlive) * time.Second,
		ReadHeaderTimeout: 30 * time.Second,
	}

	// Bind before announcing, so "Serving" is only logged once the port is
	// actually ours.
	listener, err := net.Listen("tcp", httpServer.Addr)
	if err != nil {
		return err // already names the address, e.g. "listen tcp 0.0.0.0:8001: bind: ..."
	}
	// The configured host reads better than the wildcard the OS reports
	// ("[::]"); the port is the bound one, which differs when PORT=0.
	boundPort := strconv.Itoa(listener.Addr().(*net.TCPAddr).Port)
	deps.Logger.Info("Serving MCP on http://" + net.JoinHostPort(s.Host, boundPort) + s.MCPPath)

	errs := make(chan error, 1)
	go func() {
		errs <- httpServer.Serve(listener)
	}()

	select {
	case err := <-errs:
		return err
	case <-ctx.Done():
	}

	shutdownCtx, cancel := context.WithTimeout(context.Background(), shutdownTimeout)
	defer cancel()
	if err := httpServer.Shutdown(shutdownCtx); err != nil && !errors.Is(err, http.ErrServerClosed) {
		return err
	}
	return nil
}
