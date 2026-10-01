package odas

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/schemas"
)

var discard = slog.New(slog.DiscardHandler)

// odasStub serves one canned response and records the last request.
type odasStub struct {
	status  int
	body    string
	headers map[string]string
	last    *http.Request
}

func (s *odasStub) serve(t *testing.T) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		s.last = r
		for k, v := range s.headers {
			w.Header().Set(k, v)
		}
		w.WriteHeader(s.status)
		_, _ = io.WriteString(w, s.body)
	}))
	t.Cleanup(srv.Close)
	return srv
}

func deviceClient(base string) *DeviceClassClient {
	return NewDeviceClassClient(NewHTTPClient(2*time.Second, 4), discard, DeviceClassURLs{
		CollectionURL: base + "/api/v1/device-classes",
		SearchURL:     base + "/api/v1/device-classes/search",
		VendorsPath:   "/vendors",
		HealthURL:     base + "/health",
	})
}

func toolMessage(t *testing.T, err error) string {
	t.Helper()
	var toolErr *ToolError
	if !errors.As(err, &toolErr) {
		t.Fatalf("expected a ToolError, got %v", err)
	}
	return toolErr.Message
}

const vendorsOK = `{"respcode":200,"payload":{"vendors":["TI","ADI"]},"message":"OK","traceId":"t"}`

func TestGetSuccessSendsBearerToken(t *testing.T) {
	stub := &odasStub{status: 200, body: vendorsOK}
	srv := stub.serve(t)
	out, err := deviceClient(srv.URL).ListDeviceClassVendors(context.Background(), NewSecret("tok"), "class:adc")
	if err != nil {
		t.Fatal(err)
	}
	if strings.Join(out.Vendors, ",") != "TI,ADI" {
		t.Errorf("vendors = %v", out.Vendors)
	}
	if got := stub.last.Header.Get("Authorization"); got != "Bearer tok" {
		t.Errorf("Authorization = %q", got)
	}
	if got := stub.last.URL.EscapedPath(); got != "/api/v1/device-classes/class:adc/vendors" {
		t.Errorf("path = %q", got)
	}
}

func TestGetErrorMapping(t *testing.T) {
	cases := []struct {
		name   string
		status int
		body   string
		want   string
	}{
		{"401 with message", 401, `{"message":"Unauthorized"}`,
			"Unauthorized Supply a valid ODAS token on the X-ODAS-Token request header."},
		{"401 bare", 401, ``,
			"The device-class API rejected the credential. Supply a valid ODAS token on the X-ODAS-Token request header."},
		{"404 payload message wins", 404, `{"payload":{"message":"Device class x not found"},"message":"Not Found","traceId":"t-1"}`,
			"Device class x not found (HTTP 404)"},
		{"400 envelope message", 400, `{"message":"Bad id"}`, "Bad id (HTTP 400)"},
		{"422 not json", 422, `nope`, "The device-class API rejected the request (HTTP 422)."},
		{"500", 500, `kaboom`,
			"The device-class API is unavailable. This is a service problem, not a bad request — retry shortly rather than changing the arguments."},
		{"200 missing required field", 200, `{"payload":{"node":{"id":"x"}}}`,
			"The device-class API returned a response that does not match the expected shape. Treat this as a service problem, not a bad request."},
		{"200 null payload", 200, `{"payload":null}`,
			"The device-class API returned a response that does not match the expected shape. Treat this as a service problem, not a bad request."},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			srv := (&odasStub{status: c.status, body: c.body}).serve(t)
			_, err := deviceClient(srv.URL).GetDeviceClass(context.Background(), NewSecret("tok"), "x")
			if got := toolMessage(t, err); got != c.want {
				t.Errorf("message = %q\nwant      %q", got, c.want)
			}
		})
	}
}

func TestRedirectIsNotFollowed(t *testing.T) {
	stub := &odasStub{status: 302, headers: map[string]string{"Location": "https://elsewhere.example/steal"}}
	srv := stub.serve(t)
	_, err := deviceClient(srv.URL).GetDeviceClass(context.Background(), NewSecret("tok"), "x")
	// Read like any other non-error response: its empty payload is malformed.
	if got := toolMessage(t, err); !strings.Contains(got, "does not match the expected shape") {
		t.Errorf("message = %q", got)
	}
}

func TestUnconfiguredAndUnreachable(t *testing.T) {
	_, err := deviceClient("").GetDeviceClass(context.Background(), NewSecret("tok"), "x")
	if got := toolMessage(t, err); got != "The device-class API is not configured: set ODAS_BASE_URL in the environment. Until then this tool cannot return data." {
		t.Errorf("unconfigured message = %q", got)
	}

	srv := httptest.NewServer(http.NotFoundHandler())
	base := srv.URL
	srv.Close() // nothing listens there now
	_, err = deviceClient(base).GetDeviceClass(context.Background(), NewSecret("tok"), "x")
	if got := toolMessage(t, err); !strings.HasPrefix(got, "The device-class API is unavailable.") {
		t.Errorf("unreachable message = %q", got)
	}
}

func TestCheckHealth(t *testing.T) {
	if ok, detail := deviceClient("").CheckHealth(context.Background()); ok || detail != "ODAS_BASE_URL is not set" {
		t.Errorf("unconfigured health = %v %q", ok, detail)
	}

	stub := &odasStub{status: 200, body: `{"status":"ok"}`}
	srv := stub.serve(t)
	if ok, detail := deviceClient(srv.URL).CheckHealth(context.Background()); !ok || detail != "reachable at "+srv.URL+"/health" {
		t.Errorf("health = %v %q", ok, detail)
	}
	if stub.last.Header.Get("Authorization") != "" {
		t.Error("health probe must not send a credential")
	}

	failing := (&odasStub{status: 503}).serve(t)
	if ok, detail := deviceClient(failing.URL).CheckHealth(context.Background()); ok || !strings.HasSuffix(detail, "returned HTTP 503") {
		t.Errorf("failing health = %v %q", ok, detail)
	}
}

func TestListDeviceClassesQuery(t *testing.T) {
	stub := &odasStub{status: 200, body: `{"payload":{"nodes":[]}}`}
	srv := stub.serve(t)
	parent := "group:analog"
	out, err := deviceClient(srv.URL).ListDeviceClasses(context.Background(), NewSecret("tok"), &parent, 2, nil)
	if err != nil {
		t.Fatal(err)
	}
	if got := stub.last.URL.RawQuery; got != "parent_id=group%3Aanalog&depth=2" {
		t.Errorf("query = %q", got)
	}
	if out.Nodes == nil || out.NextCursor != nil {
		t.Errorf("output = %+v", out)
	}
	var _ schemas.ListDeviceClassesOutput = out
}
