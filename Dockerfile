# === build ===
FROM golang:1.26-bookworm AS build

WORKDIR /src

# ---- dependencies first, so they cache across source changes ----
COPY go.mod go.sum ./
RUN go mod download

COPY cmd ./cmd
COPY internal ./internal
COPY orivmcp ./orivmcp

# The service version reported to MCP clients and telemetry.
ARG APP_VERSION=0.1.0

# ---- static binary: runs on a base image with no libc ----
RUN CGO_ENABLED=0 GOOS=linux go build \
    -trimpath \
    -buildvcs=false \
    -ldflags "-s -w -X main.Version=${APP_VERSION}" \
    -o /out/oriv-mcp ./cmd/oriv-mcp \
    && mkdir -p /out/logs

# === runtime ===
FROM gcr.io/distroless/static-debian12

ARG BUILD_DATE
ARG GIT_SHA
ARG VERSION

LABEL org.opencontainers.image.title="ORIV MCP" \
    org.opencontainers.image.description="Oriv Mcp server" \
    org.opencontainers.image.vendor="Oriv" \
    org.opencontainers.image.created="${BUILD_DATE}" \
    org.opencontainers.image.revision="${GIT_SHA}" \
    org.opencontainers.image.version="${VERSION}"

WORKDIR /app

COPY --from=build /out/oriv-mcp /app/oriv-mcp
# Logs go to /app/logs unless LOG_FILE_PATH says otherwise.
COPY --from=build --chown=10001:10001 /out/logs /app/logs

# ---- non-root ----
USER 10001:10001

# ---- expose port if this is an API ----
# EXPOSE 8000

# ---- runtime command ----
ENTRYPOINT ["/app/oriv-mcp"]
