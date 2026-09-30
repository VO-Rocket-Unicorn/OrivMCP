package server

import (
	"context"
	"encoding/json"
	"io"
	"log/slog"
	"net"
	"net/http"
	"net/http/httptest"
	"slices"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/sdk/trace/tracetest"

	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/capabilities"
	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/config"
	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/odas"
)

// mockODAS answers the handful of routes the integration test calls.
func mockODAS(t *testing.T) *httptest.Server {
	t.Helper()
	respond := func(w http.ResponseWriter, payload any) {
		_ = json.NewEncoder(w).Encode(map[string]any{"respcode": 200, "payload": payload})
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, _ *http.Request) {})
	mux.HandleFunc("GET /api/v1/device-classes", func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer tok" {
			w.WriteHeader(http.StatusUnauthorized)
			return
		}
		respond(w, map[string]any{"nodes": []any{map[string]any{
			"id": "group:analog", "name": "Analog", "description": "d", "childCount": 1, "path": []string{"group:analog"},
		}}})
	})
	mux.HandleFunc("GET /api/v1/projects/{project}/requirements/{id}", func(w http.ResponseWriter, r *http.Request) {
		respond(w, map[string]any{
			"requirementId": r.PathValue("id"), "name": "REQ-2", "statement": "full", "rationale": "why",
			"level": "SYSTEM", "type": "FUNCTIONAL", "isAtomic": false, "altitude": "system", "childCount": 0,
			"parent": map[string]any{"requirementId": "r1"}, "project": r.PathValue("project"),
		})
	})
	mux.HandleFunc("GET /api/v1/projects/{project}/requirements/{id}/ancestors", func(w http.ResponseWriter, _ *http.Request) {
		respond(w, map[string]any{"items": []any{map[string]any{"requirementId": "r1", "name": "REQ-1"}}})
	})
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	return srv
}

func newTestServer(t *testing.T) *httptest.Server {
	t.Helper()
	odasSrv := mockODAS(t)
	settings, err := config.LoadFrom([]string{
		"OTEL_URL=http://127.0.0.1:1",
		"ODAS_BASE_URL=" + odasSrv.URL,
		`ALLOWED_HOSTS=["127.0.0.1"]`,
		`ALLOWED_ORIGINS=["http://localhost"]`,
	}, nil)
	if err != nil {
		t.Fatal(err)
	}
	logger := slog.New(slog.DiscardHandler)
	httpClient := odas.NewHTTPClient(5*time.Second, 4)
	urls := settings.URLs
	deps := Deps{
		Settings: settings,
		Logger:   logger,
		Version:  "test",
		Clients: capabilities.Clients{
			DeviceClass: odas.NewDeviceClassClient(httpClient, logger, odas.DeviceClassURLs{
				CollectionURL: urls.DeviceClassesURL(), SearchURL: urls.DeviceClassesSearchURL(),
				VendorsPath: urls.VendorsPath, HealthURL: urls.OdasHealthURL(),
			}),
			ArchitectureSelection: odas.NewArchitectureSelectionClient(httpClient, logger, odas.ArchitectureSelectionURLs{
				DecisionTreesURL: urls.DecisionTreesURL(), TaxonomiesURL: urls.TaxonomiesURL(), HealthURL: urls.OdasHealthURL(),
			}),
			Requirement: odas.NewRequirementClient(httpClient, logger, odas.RequirementURLs{
				ProjectsURL: urls.ProjectsURL(), RequirementsPath: urls.RequirementsPath, AncestorsPath: urls.AncestorsPath,
			}),
		},
	}
	srv := httptest.NewServer(NewHTTPHandler(deps, NewMCPServer(deps)))
	t.Cleanup(srv.Close)
	return srv
}

// withHeaders adds fixed headers to every request, as an MCP host would.
type withHeaders map[string]string

func (h withHeaders) RoundTrip(r *http.Request) (*http.Response, error) {
	r = r.Clone(r.Context())
	for k, v := range h {
		r.Header.Set(k, v)
	}
	return http.DefaultTransport.RoundTrip(r)
}

func connect(t *testing.T, endpoint string, headers withHeaders) *mcp.ClientSession {
	t.Helper()
	client := mcp.NewClient(&mcp.Implementation{Name: "test", Version: "1"}, nil)
	session, err := client.Connect(context.Background(), &mcp.StreamableClientTransport{
		Endpoint:   endpoint,
		HTTPClient: &http.Client{Transport: headers},
	}, nil)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = session.Close() })
	return session
}

func text(result *mcp.CallToolResult) string {
	if len(result.Content) == 0 {
		return ""
	}
	if tc, ok := result.Content[0].(*mcp.TextContent); ok {
		return tc.Text
	}
	return ""
}

func TestEndToEnd(t *testing.T) {
	recorder := tracetest.NewSpanRecorder()
	provider := sdktrace.NewTracerProvider(sdktrace.WithSpanProcessor(recorder))
	previous := otel.GetTracerProvider()
	otel.SetTracerProvider(provider)
	t.Cleanup(func() { otel.SetTracerProvider(previous) })

	srv := newTestServer(t)
	ctx := context.Background()
	session := connect(t, srv.URL+"/mcp", withHeaders{"X-ODAS-Token": "tok", "X-Project-Id": "proj 1"})

	if got := session.InitializeResult().ServerInfo.Name; got != "OrivMCP" {
		t.Errorf("server name = %q", got)
	}

	tools, err := session.ListTools(ctx, nil)
	if err != nil {
		t.Fatal(err)
	}
	var names []string
	for _, tool := range tools.Tools {
		names = append(names, tool.Name)
	}
	slices.Sort(names)
	want := []string{
		"get_decision_tree", "get_decision_tree_node", "get_device_class", "list_device_class_vendors",
		"list_device_classes", "requirement_tree_children", "requirement_tree_node", "requirement_tree_roots",
		"requirement_tree_search", "resolve_architecture", "search_device_classes",
	}
	if !slices.Equal(names, want) {
		t.Errorf("tools = %v", names)
	}

	t.Run("structured result", func(t *testing.T) {
		result, err := session.CallTool(ctx, &mcp.CallToolParams{Name: "list_device_classes"})
		if err != nil {
			t.Fatal(err)
		}
		if result.IsError {
			t.Fatalf("unexpected error: %s", text(result))
		}
		structured, _ := json.Marshal(result.StructuredContent)
		if !strings.Contains(string(structured), `"childCount":1`) || !strings.Contains(string(structured), `"nextCursor":null`) {
			t.Errorf("structured = %s", structured)
		}
		if !strings.Contains(text(result), "\n  \"nodes\": [") {
			t.Errorf("text is not the pretty-printed object: %s", text(result))
		}
	})

	t.Run("requirement node reads the project header", func(t *testing.T) {
		result, err := session.CallTool(ctx, &mcp.CallToolParams{Name: "requirement_tree_node", Arguments: map[string]any{"requirementId": "r2"}})
		if err != nil || result.IsError {
			t.Fatalf("call failed: %v %s", err, text(result))
		}
		structured, _ := json.Marshal(result.StructuredContent)
		for _, want := range []string{`"parentId":"r1"`, `"path":["r1"]`, `"rationale":"why"`} {
			if !strings.Contains(string(structured), want) {
				t.Errorf("structured %s lacks %s", structured, want)
			}
		}
	})

	t.Run("invalid arguments are a tool error", func(t *testing.T) {
		result, err := session.CallTool(ctx, &mcp.CallToolParams{Name: "list_device_classes", Arguments: map[string]any{"depth": 9}})
		if err != nil {
			t.Fatal(err)
		}
		if !result.IsError || !strings.Contains(text(result), "Input should be less than or equal to 3") {
			t.Errorf("result = %v %q", result.IsError, text(result))
		}
	})

	t.Run("unknown tool is a tool error", func(t *testing.T) {
		result, err := session.CallTool(ctx, &mcp.CallToolParams{Name: "nope"})
		if err != nil {
			t.Fatal(err)
		}
		if !result.IsError || text(result) != "Unknown tool: nope" {
			t.Errorf("result = %v %q", result.IsError, text(result))
		}
	})

	t.Run("missing credential header", func(t *testing.T) {
		anonymous := connect(t, srv.URL+"/mcp", withHeaders{})
		result, err := anonymous.CallTool(ctx, &mcp.CallToolParams{Name: "requirement_tree_roots"})
		if err != nil {
			t.Fatal(err)
		}
		want := "Error executing tool requirement_tree_roots: Missing the X-ODAS-Token request header. " + odas.TokenHint
		if !result.IsError || text(result) != want {
			t.Errorf("result = %v %q", result.IsError, text(result))
		}
	})

	t.Run("spans", func(t *testing.T) {
		var found, errored bool
		for _, span := range recorder.Ended() {
			attrs := map[attribute.Key]string{}
			for _, kv := range span.Attributes() {
				attrs[kv.Key] = kv.Value.String()
			}
			switch span.Name() {
			case "tools/call list_device_classes":
				if attrs["gen_ai.tool.name"] == "list_device_classes" && attrs["mcp.method.name"] == "tools/call" {
					found = true
				}
			case "tools/call nope":
				errored = span.Status().Code == codes.Error && attrs["error.type"] == "tool_error"
			}
		}
		if !found || !errored {
			t.Errorf("spans: found tool span %v, error span %v", found, errored)
		}
	})
}

func TestServeHTTPReportsBusyPortWithoutAnnouncing(t *testing.T) {
	busy, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer busy.Close()
	port := busy.Addr().(*net.TCPAddr).Port

	var logs strings.Builder
	settings := &config.Settings{Server: config.ServerSettings{Host: "127.0.0.1", Port: port, MCPPath: "/mcp"}}
	deps := Deps{Settings: settings, Logger: slog.New(slog.NewTextHandler(&logs, nil))}

	err = ServeHTTP(context.Background(), deps, http.NotFoundHandler())
	if err == nil || !strings.Contains(err.Error(), "listen tcp 127.0.0.1:") {
		t.Errorf("error = %v", err)
	}
	if strings.Contains(logs.String(), "Serving MCP") {
		t.Errorf("announced serving on a port it never bound:\n%s", logs.String())
	}
}

func TestServeHTTPAnnouncesAfterBinding(t *testing.T) {
	var logs syncBuilder
	settings := &config.Settings{Server: config.ServerSettings{Host: "127.0.0.1", Port: 0, MCPPath: "/mcp"}}
	deps := Deps{Settings: settings, Logger: slog.New(slog.NewTextHandler(&logs, nil))}

	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() { done <- ServeHTTP(ctx, deps, http.NotFoundHandler()) }()

	// Port 0 means "any free port"; the log must name the one really bound.
	deadline := time.Now().Add(5 * time.Second)
	for !strings.Contains(logs.String(), "Serving MCP on http://127.0.0.1:") {
		if time.Now().After(deadline) {
			t.Fatalf("never announced; logs:\n%s", logs.String())
		}
		time.Sleep(10 * time.Millisecond)
	}
	if strings.Contains(logs.String(), "127.0.0.1:0/mcp") {
		t.Errorf("logged the requested port, not the bound one:\n%s", logs.String())
	}
	cancel()
	if err := <-done; err != nil {
		t.Errorf("shutdown error = %v", err)
	}
}

// syncBuilder is a strings.Builder safe to write from one goroutine and read
// from another.
type syncBuilder struct {
	mu sync.Mutex
	b  strings.Builder
}

func (s *syncBuilder) Write(p []byte) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.b.Write(p)
}

func (s *syncBuilder) String() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.b.String()
}

func TestHTTPRoutesAndGuard(t *testing.T) {
	srv := newTestServer(t)
	initialize := `{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"t","version":"1"}}}`
	post := func(path string, headers map[string]string) (int, string) {
		req, _ := http.NewRequest(http.MethodPost, srv.URL+path, strings.NewReader(initialize))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Accept", "application/json, text/event-stream")
		for k, v := range headers {
			if k == "Host" {
				req.Host = v
			} else {
				req.Header.Set(k, v)
			}
		}
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			t.Fatal(err)
		}
		defer resp.Body.Close()
		body, _ := io.ReadAll(resp.Body)
		return resp.StatusCode, strings.TrimSpace(string(body))
	}

	resp, err := http.Get(srv.URL + HealthPath)
	if err != nil {
		t.Fatal(err)
	}
	body, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	if resp.StatusCode != 200 || strings.TrimSpace(string(body)) != `{"status":"ok"}` {
		t.Errorf("health = %d %s", resp.StatusCode, body)
	}

	cases := []struct {
		name    string
		path    string
		headers map[string]string
		status  int
		body    string
	}{
		{"mcp path", "/mcp", nil, 200, ""},
		{"root alias", "/", nil, 200, ""},
		{"bad host", "/mcp", map[string]string{"Host": "evil.example"}, 421, "Invalid Host header"},
		{"bad origin", "/mcp", map[string]string{"Origin": "http://evil.example"}, 403, "Invalid Origin header"},
		{"allowed origin, any port", "/mcp", map[string]string{"Origin": "http://localhost:3000"}, 200, ""},
		{"bad content type", "/mcp", map[string]string{"Content-Type": "text/plain"}, 400, "Invalid Content-Type header"},
		{"unknown path", "/elsewhere", nil, 404, ""},
	}
	for _, c := range cases {
		status, body := post(c.path, c.headers)
		if status != c.status || (c.body != "" && body != c.body) {
			t.Errorf("%s: got %d %q, want %d %q", c.name, status, body, c.status, c.body)
		}
	}
}
