# OrivMCP

The Oriv MCP server. It serves read-only tools over the
[Model Context Protocol](https://modelcontextprotocol.io) (streamable HTTP) that
let a model browse ODAS: the device-class taxonomy, the AI decision trees for
architecture selection, and a project's requirement tree.

The caller supplies its own credentials per request. This server holds none:

| Header         | Used by                   | Purpose                                     |
| -------------- | ------------------------- | ------------------------------------------- |
| `X-ODAS-Token` | every ODAS-backed tool    | forwarded to ODAS as `Authorization: Bearer` |
| `X-Project-Id` | the `requirement_tree_*` tools | the project the requirement tree belongs to |

## Tools

| Tag            | Tools |
| -------------- | ----- |
| (none)         | `list_device_classes`, `search_device_classes`, `get_device_class`, `list_device_class_vendors` |
| `architecture` | `get_decision_tree`, `get_decision_tree_node`, `resolve_architecture` |
| `requirements` | `requirement_tree_roots`, `requirement_tree_children`, `requirement_tree_search`, `requirement_tree_node` |

There is also a demo prompt, `flight_planner`, and a demo resource template,
`file://documents/{airport}`.

## Running locally

The commands below are for PowerShell, run from the repo root. In bash, use `cp`
instead of `Copy-Item`, `curl` instead of `curl.exe`, and `\` instead of `` ` ``
for line continuation.

### 1. Prerequisites

| Tool | Version | Needed for |
| ---- | ------- | ---------- |
| Go | 1.26 | building and running the server |
| Node.js | 22.19.0 or newer | MCP Inspector (testing only) |

### 2. Configure

```powershell
Copy-Item .env.example .env
```

Then edit `.env`. `.env.example` documents every setting; for local work these are
the ones that matter:

```ini
ENVIRONMENT=sandbox                       # logs to the console at DEBUG, no log files
PORT=8000                                 # any free port
ALLOWED_HOSTS=["localhost","127.0.0.1"]   # must be a JSON array, not a,b
ODAS_BASE_URL=https://dev-api.oriv.studio
OTEL_URL=http://localhost:4318            # required, even with no collector running
```

With no OpenTelemetry collector running you will see occasional
`failed to upload metrics` lines. They are harmless.

Outside the sandbox, the server logs at INFO to a rotating file under
`LOG_FILE_PATH` and to the collector (OTLP/HTTP at `OTEL_URL`), which also
receives traces (one span per MCP message) and metrics.

### 3. Start the server

```powershell
go run ./cmd/oriv-mcp
```

It is up once it logs `Serving MCP on http://0.0.0.0:<PORT>/mcp`. Leave this
terminal open; `Ctrl+C` stops the server.

`go run ./cmd/oriv-mcp --transport=stdio` serves over stdio instead. Stdio has no
request headers, so the ODAS-backed tools report the missing credential.

### 4. Check it is running

```powershell
curl.exe http://localhost:8000/health     # {"status":"ok"}
```

Opening the bare port in a browser does not show a page. `/` and `/mcp` are the
MCP endpoint, which only talks to MCP clients:

| URL | Response | Meaning |
| --- | -------- | ------- |
| `http://localhost:<PORT>/health` | `{"status":"ok"}` | the server is up |
| `http://localhost:<PORT>/` or `/mcp` | `400 Accept must contain 'text/event-stream' for GET requests` | also up; it is just not a web page |
| any of the above | connection refused | the server is not running, or is on another port |

## Testing with MCP Inspector

[MCP Inspector](https://modelcontextprotocol.io/docs/2026-07-28/tools/inspector)
is the reference client for testing MCP servers. Install it once:

```powershell
npm install -g @modelcontextprotocol/inspector   # provides the mcp-inspector command
```

### Headers

Tools read the caller's credentials from request headers, and the Inspector sends
them with `--header "Name: Value"`. Repeat the flag once per header:

| Header | Needed by |
| ------ | --------- |
| `X-ODAS-Token` | every tool |
| `X-Project-Id` | the four `requirement_tree_*` tools |

A missing header comes back as a tool error such as
`Missing the X-Project-Id request header.`

### Web UI

With the server running, in a second terminal:

```powershell
mcp-inspector --server-url http://localhost:8000/mcp --transport http `
  --header "X-ODAS-Token: <your-token>" `
  --header "X-Project-Id: <your-project-id>"
```

It prints a `http://127.0.0.1:6274?MCP_INSPECTOR_API_TOKEN=...` link. Open it,
click **Connect**, then use the **Tools** tab: pick a tool, fill in its arguments
and click Run.

Headers are read only when the Inspector starts. To change one, for example to
look at another project, stop the Inspector with `Ctrl+C`, relaunch it with the
new value, and open the new link it prints.

### Command line

The same flags, with a method to call instead of the UI:

```powershell
# list the tools
mcp-inspector --cli --server-url http://localhost:8000/mcp --transport http --method tools/list

# call a tool
mcp-inspector --cli --server-url http://localhost:8000/mcp --transport http `
  --header "X-ODAS-Token: <your-token>" `
  --header "X-Project-Id: <your-project-id>" `
  --method tools/call --tool-name requirement_tree_roots

# call a tool with arguments
mcp-inspector --cli --server-url http://localhost:8000/mcp --transport http `
  --header "X-ODAS-Token: <your-token>" `
  --method tools/call --tool-name search_device_classes --tool-arg query=adc
```

`--tui` instead of `--cli` gives an interactive terminal UI.

## Troubleshooting

| Symptom | Cause | Fix |
| ------- | ----- | --- |
| `listen tcp 0.0.0.0:<PORT>: bind: Only one usage of each socket address ...` | Another process already holds the port, usually an earlier `go run` still running in another terminal. | Stop that one with `Ctrl+C`, or find it (next row) and stop it, or change `PORT`. |
| Not sure what holds a port | | `Get-NetTCPConnection -State Listen -LocalPort <PORT> \| Select-Object OwningProcess`, then `Stop-Process -Id <pid>` |
| `invalid configuration: ... OTEL_URL: field required` | `OTEL_URL` is missing from `.env`. | Set it; any URL works locally. |
| `ALLOWED_HOSTS: error parsing value` | A list was written as `a,b`. | Use a JSON array: `["localhost","127.0.0.1"]`. |
| `421 Invalid Host header` | The host name you connect with is not in `ALLOWED_HOSTS`. | Add it (`localhost` and `127.0.0.1` for local work). |
| `403 Invalid Origin header` | A browser-based client sent an `Origin` not in `ALLOWED_ORIGINS`. | Add it, e.g. `["http://localhost"]`. |
| `Missing the X-ODAS-Token request header` / `Missing the X-Project-Id request header` | The client did not send that header. | Pass it with `--header` and restart the Inspector. |
| `... (HTTP 401)` or `... (HTTP 404)` from a tool | ODAS rejected the request: an invalid token, or a route or id it does not know. The text is ODAS's own. | Check the token and `ODAS_BASE_URL`. |
| `ODAS preflight FAILED` at startup | ODAS was not reachable at `ODAS_BASE_URL` + `ODAS_HEALTH_PATH`. | Check the URL. The server still starts; ODAS tools fail until ODAS is reachable. |

## Developing

```bash
gofmt -l cmd internal       # should print nothing
go vet ./...
go test ./...
```

| Package                 | What it holds |
| ----------------------- | ------------- |
| `cmd/oriv-mcp`          | entry point: config → telemetry → clients → server |
| `internal/config`       | settings, read from the environment and `.env` |
| `internal/telemetry`    | OpenTelemetry providers and the logger |
| `internal/odas`         | outbound ODAS clients: envelope, error mapping, URL building |
| `internal/schemas`      | ODAS wire types and tool output types |
| `internal/capabilities` | the tools, prompt and resource, and argument validation |
| `internal/server`       | HTTP routing, Host/Origin allowlist, tracing, lifecycle |

## Docker

```bash
docker build -t oriv-mcp .
docker run --env-file .env -p 8000:8000 oriv-mcp
```

The image is a static binary on `distroless/static`, running as uid 10001.

## Legacy

The original Python implementation is kept in [`legacy/`](legacy/README.md) for
reference. It is not built, tested or deployed.
