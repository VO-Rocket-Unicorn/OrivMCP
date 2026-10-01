package orivmcp

import (
	"context"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// mockODAS answers the startup probe.
func mockODAS(t *testing.T) *httptest.Server {
	t.Helper()
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", func(http.ResponseWriter, *http.Request) {})
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	return srv
}

func environ(t *testing.T, extra ...string) []string {
	t.Helper()
	return append([]string{
		"OTEL_URL=http://127.0.0.1:1",
		"ODAS_BASE_URL=" + mockODAS(t).URL,
		`ALLOWED_HOSTS=["127.0.0.1"]`,
		"ENVIRONMENT=development",
		"LOG_FILE_PATH=" + t.TempDir(),
	}, extra...)
}

func loopback(t *testing.T) net.Listener {
	t.Helper()
	listener, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	return listener
}

func shutdown(t *testing.T, srv *Server) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		t.Errorf("shutdown error = %v", err)
	}
	select {
	case <-srv.Done():
	default:
		t.Error("Shutdown returned before Done was closed")
	}
}

func TestStartServesOnTheGivenListener(t *testing.T) {
	listener := loopback(t)
	env := environ(t)
	logDir := strings.TrimPrefix(env[len(env)-1], "LOG_FILE_PATH=")

	srv, err := Start(context.Background(), Options{Environ: env, Listener: listener, Version: "test"})
	if err != nil {
		t.Fatal(err)
	}
	want := "http://" + listener.Addr().String() + "/mcp"
	if srv.URL() != want {
		t.Errorf("URL = %q, want %q", srv.URL(), want)
	}

	// Reachable as soon as Start returns.
	resp, err := http.Get(strings.TrimSuffix(srv.URL(), "/mcp") + "/health")
	if err != nil {
		t.Fatal(err)
	}
	body, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK || strings.TrimSpace(string(body)) != `{"status":"ok"}` {
		t.Errorf("health = %d %s", resp.StatusCode, body)
	}

	client := mcp.NewClient(&mcp.Implementation{Name: "test", Version: "1"}, nil)
	session, err := client.Connect(context.Background(), &mcp.StreamableClientTransport{Endpoint: srv.URL()}, nil)
	if err != nil {
		t.Fatal(err)
	}
	if got := session.InitializeResult().ServerInfo.Version; got != "test" {
		t.Errorf("server version = %q", got)
	}
	tools, err := session.ListTools(context.Background(), nil)
	if err != nil {
		t.Fatal(err)
	}
	if len(tools.Tools) == 0 {
		t.Error("no tools listed")
	}
	_ = session.Close()

	shutdown(t, srv)

	// The listener is released with the server.
	if _, err := http.Get(strings.TrimSuffix(srv.URL(), "/mcp") + "/health"); err == nil {
		t.Error("still serving after Shutdown")
	}
	// The log file is written and closed: on Windows the TempDir cleanup
	// fails if it is still open.
	logged, err := os.ReadFile(filepath.Join(logDir, "OrivMCP.log"))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(logged), "Serving MCP on "+srv.URL()) {
		t.Errorf("log lacks the serving line:\n%s", logged)
	}
}

func TestStartBindsTheConfiguredAddressWithoutAListener(t *testing.T) {
	srv, err := Start(context.Background(), Options{Environ: environ(t, "HOST=127.0.0.1", "PORT=0")})
	if err != nil {
		t.Fatal(err)
	}
	defer shutdown(t, srv)
	if !strings.HasPrefix(srv.URL(), "http://127.0.0.1:") || strings.HasPrefix(srv.URL(), "http://127.0.0.1:0/") {
		t.Errorf("URL = %q", srv.URL())
	}
}

func TestStartRejectsBadConfigurationAndReleasesTheListener(t *testing.T) {
	listener := loopback(t)
	addr := listener.Addr().String()

	_, err := Start(context.Background(), Options{
		Environ:  []string{`ALLOWED_HOSTS=["127.0.0.1"]`}, // no OTEL_URL
		Listener: listener,
	})
	if err == nil || !strings.Contains(err.Error(), "OTEL_URL") {
		t.Fatalf("error = %v", err)
	}
	again, err := net.Listen("tcp4", addr)
	if err != nil {
		t.Fatalf("listener was not released: %v", err)
	}
	_ = again.Close()
}

func TestCancellingTheContextStopsTheServer(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	srv, err := Start(ctx, Options{Environ: environ(t), Listener: loopback(t)})
	if err != nil {
		t.Fatal(err)
	}
	cancel()
	select {
	case <-srv.Done():
	case <-time.After(30 * time.Second):
		t.Fatal("server did not stop after its context was cancelled")
	}
	if err := srv.Err(); err != nil {
		t.Errorf("Err = %v", err)
	}
	// A second Shutdown is a no-op.
	shutdown(t, srv)
}

func TestEndpointURL(t *testing.T) {
	cases := []struct {
		addr net.Addr
		want string
	}{
		{&net.TCPAddr{IP: net.IPv4(127, 0, 0, 1), Port: 8001}, "http://127.0.0.1:8001/mcp"},
		{&net.TCPAddr{IP: net.IPv6loopback, Port: 8001}, "http://[::1]:8001/mcp"},
		{&net.TCPAddr{IP: net.IPv4zero, Port: 8001}, "http://127.0.0.1:8001/mcp"},
		{&net.TCPAddr{IP: net.IPv6unspecified, Port: 8001}, "http://127.0.0.1:8001/mcp"},
		{&net.TCPAddr{Port: 8001}, "http://127.0.0.1:8001/mcp"},
	}
	for _, c := range cases {
		if got := endpointURL(c.addr, "/mcp"); got != c.want {
			t.Errorf("endpointURL(%v) = %q, want %q", c.addr, got, c.want)
		}
	}
}
