// Package odas holds the outbound clients for ODAS, which serves the
// device-class taxonomy, the AI decision trees and the requirement tree
// behind one base URL and one credential.
//
// The credential is never held here. It arrives per request from the caller
// and is passed into each call, which makes tenancy the caller's to prove
// rather than this server's to assume.
package odas

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"strconv"
	"strings"
	"time"
)

const (
	// BaseURLEnvVar names the setting an unconfigured client asks for.
	BaseURLEnvVar = "ODAS_BASE_URL"

	// TokenHeader is where the caller supplies its own ODAS credential; the
	// server holds none.
	TokenHeader = "X-ODAS-Token"

	// CredentialHint is appended to a 401, which the caller must fix.
	CredentialHint = "Supply a valid ODAS token on the " + TokenHeader + " request header."

	// TokenHint explains a missing TokenHeader.
	TokenHint = "The caller must supply its ODAS token on that header; this server holds no credentials of its own."
)

const (
	authorizationHeader = "Authorization"
	bearerPrefix        = "Bearer"
	absoluteURLPrefix   = "http"

	// Every response is wrapped: {respcode, payload, message, traceId}. The
	// data the tools care about, and on a 400/404 the actionable error text,
	// live under payload. respcode is not load-bearing; HTTP status is.
	payloadKey = "payload"
	messageKey = "message"
	traceIDKey = "traceId"

	// logBodyLimit caps how much of a 5xx body is logged.
	logBodyLimit = 500
	// maxResponseBytes guards against an unbounded response body.
	maxResponseBytes = 64 << 20
)

// Secret is a credential. It prints masked, so it cannot surface through a
// log line or a formatted error on its way to the service that needs it.
type Secret struct{ value string }

func NewSecret(value string) Secret { return Secret{value: value} }

func (s Secret) Reveal() string             { return s.value }
func (Secret) String() string               { return "**********" }
func (Secret) GoString() string             { return "odas.Secret(**********)" }
func (Secret) LogValue() slog.Value         { return slog.StringValue("**********") }
func (Secret) MarshalJSON() ([]byte, error) { return []byte(`"**********"`), nil }

// ToolError is a failure whose message is safe and useful for a model to
// read. Tools return it as an error result carrying just that message.
type ToolError struct{ Message string }

func (e *ToolError) Error() string { return e.Message }

func toolError(format string, args ...any) *ToolError {
	return &ToolError{Message: fmt.Sprintf(format, args...)}
}

// NewHTTPClient is the one pooled HTTP client every outbound client shares.
//
// Redirects are not followed, as with httpx, which the Python implementation
// used. A redirect response is then read like any other, and the caller's
// bearer token is never replayed to wherever a redirect points.
func NewHTTPClient(timeout time.Duration, maxConnections int) *http.Client {
	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.MaxConnsPerHost = maxConnections
	transport.MaxIdleConns = maxConnections
	transport.MaxIdleConnsPerHost = maxConnections
	return &http.Client{
		Timeout:   timeout,
		Transport: transport,
		CheckRedirect: func(*http.Request, []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}
}

// param is one query parameter. A nil value is dropped rather than sent
// empty.
type param struct {
	key   string
	value any // string, int, *string or nil
}

func encodeQuery(params []param) string {
	var parts []string
	for _, p := range params {
		var value string
		switch v := p.value.(type) {
		case nil:
			continue
		case *string:
			if v == nil {
				continue
			}
			value = *v
		case string:
			value = v
		case int:
			value = strconv.Itoa(v)
		default:
			value = fmt.Sprint(v)
		}
		parts = append(parts, queryEscape(p.key)+"="+queryEscape(value))
	}
	return strings.Join(parts, "&")
}

// apiClient issues GETs against one service and validates the result,
// turning every failure into a ToolError.
type apiClient struct {
	http           *http.Client
	logger         *slog.Logger
	serviceLabel   string
	credentialHint string
}

func newAPIClient(httpClient *http.Client, logger *slog.Logger, serviceLabel string) apiClient {
	return apiClient{http: httpClient, logger: logger, serviceLabel: serviceLabel, credentialHint: CredentialHint}
}

// ---- messages ----

func (c *apiClient) unconfigured() *ToolError {
	return toolError("The %s is not configured: set %s in the environment. Until then this tool cannot return data.",
		c.serviceLabel, BaseURLEnvVar)
}

func (c *apiClient) unavailable() *ToolError {
	return toolError("The %s is unavailable. This is a service problem, not a bad request — retry shortly rather than changing the arguments.",
		c.serviceLabel)
}

func (c *apiClient) malformed() *ToolError {
	return toolError("The %s returned a response that does not match the expected shape. Treat this as a service problem, not a bad request.",
		c.serviceLabel)
}

// ---- envelope ----

// envelope is the decoded response body, or empty when it is not a JSON object.
func envelope(body []byte) map[string]json.RawMessage {
	var env map[string]json.RawMessage
	if err := json.Unmarshal(body, &env); err != nil || env == nil {
		return map[string]json.RawMessage{}
	}
	return env
}

// payload is the envelope's payload object, or {} when it is absent or not
// an object.
func payload(env map[string]json.RawMessage) []byte {
	raw := env[payloadKey]
	var obj map[string]json.RawMessage
	if err := json.Unmarshal(raw, &obj); err != nil || obj == nil {
		return []byte("{}")
	}
	return raw
}

// truthyText renders a JSON value the way Python's truthiness and
// f-string formatting would treat it: "" for null, false, 0, "" and empty
// containers, the bare text for a string, compact JSON otherwise.
func truthyText(raw json.RawMessage) string {
	var value any
	if err := json.Unmarshal(raw, &value); err != nil {
		return ""
	}
	switch v := value.(type) {
	case nil:
		return ""
	case string:
		return v
	case bool:
		if !v {
			return ""
		}
		return "True"
	case float64:
		if v == 0 {
			return ""
		}
	case []any:
		if len(v) == 0 {
			return ""
		}
	case map[string]any:
		if len(v) == 0 {
			return ""
		}
	}
	return strings.TrimSpace(string(raw))
}

// errorText prefers payload.message, the actionable one, over the envelope's.
func errorText(env map[string]json.RawMessage) string {
	var p map[string]json.RawMessage
	if err := json.Unmarshal(env[payloadKey], &p); err == nil {
		if text := truthyText(p[messageKey]); text != "" {
			return text
		}
	}
	return truthyText(env[messageKey])
}

// ---- request ----

func (c *apiClient) reject(ctx context.Context, status int, body []byte) *ToolError {
	env := envelope(body)
	traceID := truthyText(env[traceIDKey])
	message := errorText(env)

	switch {
	case status == http.StatusUnauthorized:
		// A 401 carries no payload, and the caller, not this server, owns the
		// credential, so say which one to fix.
		if message == "" {
			message = fmt.Sprintf("The %s rejected the credential.", c.serviceLabel)
		}
		message = message + " " + c.credentialHint
	case message != "":
		// The status rides along with the service's own words: a failure has
		// to be diagnosable from the run trace alone.
		message = fmt.Sprintf("%s (HTTP %d)", message, status)
	default:
		message = fmt.Sprintf("The %s rejected the request (HTTP %d).", c.serviceLabel, status)
	}

	if traceID != "" {
		c.logger.ErrorContext(ctx, fmt.Sprintf("%s returned %d (traceId=%s)", c.serviceLabel, status, traceID))
	}
	return &ToolError{Message: message}
}

// CheckHealth probes a service's health endpoint.
//
// It never errors and never sends a credential: this runs at startup, where
// there is no caller and no token, and a dead dependency must not stop this
// server from booting.
func (c *apiClient) CheckHealth(ctx context.Context, url string) (bool, string) {
	if !strings.HasPrefix(url, absoluteURLPrefix) {
		return false, BaseURLEnvVar + " is not set"
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return false, fmt.Sprintf("unreachable at %s (%v)", url, err)
	}
	resp, err := c.http.Do(req)
	if err != nil {
		return false, fmt.Sprintf("unreachable at %s (%v)", url, err)
	}
	defer resp.Body.Close()
	_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, maxResponseBytes))
	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		return true, "reachable at " + url
	}
	return false, fmt.Sprintf("%s returned HTTP %d", url, resp.StatusCode)
}

// get issues an authenticated GET and decodes the envelope's payload into T.
func get[T any](ctx context.Context, c *apiClient, url string, token Secret, params ...param) (T, error) {
	var zero T

	// A relative URL means the base URL setting is empty.
	if !strings.HasPrefix(url, absoluteURLPrefix) {
		return zero, c.unconfigured()
	}

	target := url
	if query := encodeQuery(params); query != "" {
		target += "?" + query
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, target, nil)
	if err != nil {
		c.logger.ErrorContext(ctx, fmt.Sprintf("%s request to %s failed: %v", c.serviceLabel, url, err))
		return zero, c.unavailable()
	}
	req.Header.Set(authorizationHeader, bearerPrefix+" "+token.Reveal())

	resp, err := c.http.Do(req)
	if err != nil {
		// A cancelled caller (or a sibling read that already failed) is not a
		// service problem worth an error line.
		if ctx.Err() == nil {
			c.logger.ErrorContext(ctx, fmt.Sprintf("%s request to %s failed: %v", c.serviceLabel, url, err))
		}
		return zero, c.unavailable()
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(io.LimitReader(resp.Body, maxResponseBytes))
	if err != nil {
		c.logger.ErrorContext(ctx, fmt.Sprintf("%s request to %s failed: %v", c.serviceLabel, url, err))
		return zero, c.unavailable()
	}

	switch {
	case resp.StatusCode >= 400 && resp.StatusCode < 500:
		return zero, c.reject(ctx, resp.StatusCode, body)
	case resp.StatusCode >= 500 && resp.StatusCode < 600:
		text := string(body)
		if len(text) > logBodyLimit {
			text = text[:logBodyLimit]
		}
		traceID := truthyText(envelope(body)[traceIDKey])
		if traceID == "" {
			traceID = "None"
		}
		c.logger.ErrorContext(ctx, fmt.Sprintf("%s returned %d for %s (traceId=%s): %s",
			c.serviceLabel, resp.StatusCode, url, traceID, text))
		return zero, c.unavailable()
	}

	var result T
	if err := json.Unmarshal(payload(envelope(body)), &result); err != nil {
		c.logger.ErrorContext(ctx, fmt.Sprintf("%s response from %s did not validate: %v", c.serviceLabel, url, err))
		return zero, c.malformed()
	}
	return result, nil
}
