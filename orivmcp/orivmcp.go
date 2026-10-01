// Package orivmcp runs the Oriv MCP server inside another Go process.
//
// It is the same server the oriv-mcp binary runs: the same configuration
// variables, tools, transport guard, logging and telemetry. Only the
// lifecycle belongs to the host: it can hand in a listener it has already
// bound, and it stops the server with Shutdown instead of a signal.
//
// The server installs the OpenTelemetry globals (propagator, tracer and
// meter providers) for the process, so run at most one per process.
package orivmcp

import (
	"context"
	"errors"
	"net"
	"net/http"
	"os"
	"strconv"
	"sync"
	"time"

	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/app"
	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/config"
	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/server"
)

// DefaultVersion is reported to MCP clients and telemetry when Options
// leaves Version empty.
const DefaultVersion = "0.1.0"

// cleanupTimeout bounds the telemetry flush once serving has stopped.
const cleanupTimeout = 5 * time.Second

// Options configures Start.
type Options struct {
	// Environ is the configuration as KEY=value pairs, read exactly as the
	// binary reads its environment (names are case-insensitive). Nil means
	// os.Environ(). No .env file is read: the host decides what the server
	// sees.
	Environ []string

	// Listener, when set, is where the server is served; HOST and PORT are
	// then not used. Start takes ownership of it in every case, including
	// when it returns an error, and the server closes it when it stops.
	Listener net.Listener

	// Version is reported to MCP clients and telemetry.
	Version string
}

// Server is a running MCP server.
type Server struct {
	url    string
	cancel context.CancelFunc
	done   chan struct{}

	mu  sync.Mutex
	err error
}

// Start loads the configuration, builds the runtime and starts serving. It
// returns once the listener is bound, so the server is reachable at URL as
// soon as Start returns; it does not wait on ODAS, which is probed in the
// background.
//
// The server runs until ctx is cancelled or Shutdown is called.
func Start(ctx context.Context, opts Options) (*Server, error) {
	srv, err := start(ctx, opts)
	if err != nil && opts.Listener != nil {
		_ = opts.Listener.Close()
	}
	return srv, err
}

func start(ctx context.Context, opts Options) (*Server, error) {
	environ := opts.Environ
	if environ == nil {
		environ = os.Environ()
	}
	version := opts.Version
	if version == "" {
		version = DefaultVersion
	}

	settings, err := config.LoadFrom(environ, nil)
	if err != nil {
		return nil, err
	}

	listener := opts.Listener
	if listener == nil {
		s := settings.Server
		listener, err = net.Listen("tcp", net.JoinHostPort(s.Host, strconv.Itoa(s.Port)))
		if err != nil {
			return nil, err
		}
	}

	runCtx, cancel := context.WithCancel(ctx)
	rt, err := app.New(runCtx, settings, version)
	if err != nil {
		cancel()
		if opts.Listener == nil {
			_ = listener.Close()
		}
		return nil, err
	}

	srv := &Server{
		url:    endpointURL(listener.Addr(), settings.Server.MCPPath),
		cancel: cancel,
		done:   make(chan struct{}),
	}
	go srv.run(runCtx, rt, listener)
	return srv, nil
}

// run owns the server from Start until it has fully stopped: it serves, and
// once serving ends it waits for the ODAS probe and releases the runtime
// before closing done.
func (s *Server) run(ctx context.Context, rt *app.Runtime, listener net.Listener) {
	defer close(s.done)
	defer s.cancel()

	rt.Deps.Logger.Info("Starting up the application...")

	var preflight sync.WaitGroup
	preflight.Go(func() { rt.Preflight(ctx) })

	serveErr := server.Serve(ctx, rt.Deps, server.NewHTTPHandler(rt.Deps, rt.MCPServer), listener)
	if serveErr != nil && !errors.Is(serveErr, http.ErrServerClosed) {
		rt.Deps.Logger.Error("server stopped: " + serveErr.Error())
	} else {
		serveErr = nil
	}
	// Serving can end on its own (the listener failed); stop the probe too.
	s.cancel()
	preflight.Wait()

	rt.Deps.Logger.Info("Shutting down the application...")
	cleanupCtx, cancel := context.WithTimeout(context.WithoutCancel(ctx), cleanupTimeout)
	defer cancel()
	closeErr := rt.Close(cleanupCtx)

	s.mu.Lock()
	s.err = errors.Join(serveErr, closeErr)
	s.mu.Unlock()
}

// URL is the MCP endpoint, e.g. http://127.0.0.1:8001/mcp.
func (s *Server) URL() string { return s.url }

// Done is closed once the server has stopped and released everything it
// started.
func (s *Server) Done() <-chan struct{} { return s.done }

// Err is why the server stopped: nil after a clean shutdown. It is only
// meaningful once Done is closed.
func (s *Server) Err() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.err
}

// Shutdown stops the server: in-flight requests drain (for at most 10 s),
// then telemetry is flushed and the log file closed. It returns once all of
// that has finished, or with ctx's error if ctx ends first, in which case
// the server still finishes stopping on its own. It is safe to call more
// than once.
func (s *Server) Shutdown(ctx context.Context) error {
	s.cancel()
	select {
	case <-s.done:
		return s.Err()
	case <-ctx.Done():
		return ctx.Err()
	}
}

// endpointURL is the URL a client on this host dials. A wildcard bind
// (0.0.0.0 or [::]) is not dialable everywhere, so it is reported as the
// loopback address.
func endpointURL(addr net.Addr, path string) string {
	host, port := "127.0.0.1", ""
	if tcp, ok := addr.(*net.TCPAddr); ok {
		port = strconv.Itoa(tcp.Port)
		if len(tcp.IP) > 0 && !tcp.IP.IsUnspecified() {
			host = tcp.IP.String()
		}
	} else if h, p, err := net.SplitHostPort(addr.String()); err == nil {
		host, port = h, p
	}
	return "http://" + net.JoinHostPort(host, port) + path
}
