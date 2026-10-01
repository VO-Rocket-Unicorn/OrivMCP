package capabilities

import (
	"fmt"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/odas"
)

// Required values read off the incoming MCP request.
//
// What belongs on a header rather than in a tool argument: anything fixed for
// the caller's session. A value the model cannot vary is a value it cannot
// get wrong, and one it never has to be told.

// ProjectIDHeader names the project a call is scoped to. Deliberately not
// named after any one service: a project is the caller's context, and which
// backend happens to serve it is not the caller's concern.
const (
	ProjectIDHeader = "X-Project-Id"
	ProjectIDHint   = "The caller must supply the project id on that header. It is fixed for the session, which is why it is not a tool argument."
)

// headerValue returns a header's value, or an error message the model can
// act on. Lookup is case-insensitive. A transport without headers (stdio)
// has none to give.
func headerValue(req *mcp.CallToolRequest, header, hint string) (string, error) {
	var value string
	if req != nil && req.Extra != nil && req.Extra.Header != nil {
		value = req.Extra.Header.Get(header)
	}
	if value == "" {
		return "", &odas.ToolError{Message: fmt.Sprintf("Missing the %s request header. %s", header, hint)}
	}
	return value, nil
}

// requireHeader reads a required header that is not a credential.
func requireHeader(req *mcp.CallToolRequest, header, hint string) (string, error) {
	return headerValue(req, header, hint)
}

// requireSecretHeader reads a required header that is a credential, wrapped
// so its value cannot surface through a log line or formatted error.
func requireSecretHeader(req *mcp.CallToolRequest, header, hint string) (odas.Secret, error) {
	value, err := headerValue(req, header, hint)
	if err != nil {
		return odas.Secret{}, err
	}
	return odas.NewSecret(value), nil
}

// odasToken is the caller's ODAS credential.
func odasToken(req *mcp.CallToolRequest) (odas.Secret, error) {
	return requireSecretHeader(req, odas.TokenHeader, odas.TokenHint)
}
