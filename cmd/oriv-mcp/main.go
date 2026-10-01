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
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/joho/godotenv"
	"github.com/modelcontextprotocol/go-sdk/jsonrpc"
	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/app"
	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/config"
	"github.com/VO-Rocket-Unicorn/OrivMCP/orivmcp"
)

// Version is the service version reported to MCP clients and telemetry.
// Release builds set it with -ldflags "-X main.Version=...".
var Version = orivmcp.DefaultVersion

const (
	transportHTTP  = "http"
	transportStdio = "stdio"
)

// stdioCleanupTimeout bounds the telemetry flush after a stdio session.
const stdioCleanupTimeout = 5 * time.Second

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

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	if transport == transportStdio {
		return runStdio(ctx)
	}

	environ, err := environWithDotEnv()
	if err != nil {
		return err
	}
	srv, err := orivmcp.Start(ctx, orivmcp.Options{Environ: environ, Version: Version})
	if err != nil {
		return err
	}
	<-srv.Done()
	return srv.Err()
}

func runStdio(ctx context.Context) error {
	settings, err := config.Load()
	if err != nil {
		return err
	}
	rt, err := app.New(ctx, settings, Version)
	if err != nil {
		return err
	}
	defer func() {
		cleanupCtx, cancel := context.WithTimeout(context.WithoutCancel(ctx), stdioCleanupTimeout)
		defer cancel()
		_ = rt.Close(cleanupCtx)
	}()

	logger := rt.Deps.Logger
	logger.Info("Starting up the application...")
	defer logger.Info("Shutting down the application...")
	rt.Preflight(ctx)

	err = rt.MCPServer.Run(ctx, &mcp.StdioTransport{})
	if err != nil && !errors.Is(err, context.Canceled) && !isClientHangup(err) {
		return err
	}
	return nil
}

// environWithDotEnv is the process environment with the working directory's
// `.env` beneath it: a real environment variable wins over the file, as
// config.Load does it.
func environWithDotEnv() ([]string, error) {
	dotenv, err := godotenv.Read(config.EnvFile)
	if err != nil && !errors.Is(err, os.ErrNotExist) {
		return nil, fmt.Errorf("reading %s: %w", config.EnvFile, err)
	}
	environ := make([]string, 0, len(dotenv)+len(os.Environ()))
	for key, value := range dotenv {
		environ = append(environ, key+"="+value)
	}
	// Later pairs win in config.LoadFrom, so the real environment goes last.
	return append(environ, os.Environ()...), nil
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
