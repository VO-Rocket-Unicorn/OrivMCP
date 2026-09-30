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

## Running

Requires Go 1.26.

```bash
cp .env.example .env        # then fill in OTEL_URL, ALLOWED_HOSTS, ODAS_BASE_URL
go run ./cmd/oriv-mcp       # serves http://HOST:PORT/mcp (also aliased at /)
```

`GET /health` answers `{"status":"ok"}`. `go run ./cmd/oriv-mcp --transport=stdio`
serves over stdio instead. There are no request headers there, so the ODAS-backed
tools report the missing credential.

`.env.example` documents every setting. `ENVIRONMENT=sandbox` logs to the console at
DEBUG. Any other environment logs at INFO to a rotating file under `LOG_FILE_PATH`
and to the OpenTelemetry collector (OTLP/HTTP at `OTEL_URL`), which also receives
traces (one span per MCP message) and metrics.

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
