# lib-oriv-telemetry

Logging and OpenTelemetry tracing/metrics utilities for Oriv services.

Provides:

- Rich-formatted application loggers with optional rotating file output and OTel trace/span ID injection
- A singleton `Telemetry` bootstrap for OTLP/gRPC traces, metrics, and logs
- A provider-agnostic `ModelObservability` helper for instrumenting LLM/OCR/embedding calls via pluggable `UsagePlugin`s
- First-party plugins for DSPy predictions and Mistral OCR responses

---

## Installation

### As a library

Core install (logging + tracing + metrics, no third-party plugins):

```bash
uv add lib-oriv-telemetry
# or
pip install lib-oriv-telemetry
```

With optional plugin extras:

```bash
uv add "lib-oriv-telemetry[dspy]"      # DSPyPredictionUsagePlugin
uv add "lib-oriv-telemetry[mistral]"   # OCRUsagePlugin (Mistral)
uv add "lib-oriv-telemetry[litellm]"   # LiteLLM auto-instrumentation
uv add "lib-oriv-telemetry[all]"       # everything
```

### As a git subtree

Use this when you want the source vendored into a monorepo so changes can be committed locally and synced back upstream.

**Add the subtree** (run from the consuming repo's root):

```bash
git remote add -f lib-oriv-telemetry https://github.com/VO-Rocket-Unicorn/lib-oriv-telemetry.git
git subtree add --prefix=libs/lib-oriv-telemetry lib-oriv-telemetry main --squash
```

**Pull upstream updates:**

```bash
git fetch lib-oriv-telemetry main
git subtree pull --prefix=libs/lib-oriv-telemetry lib-oriv-telemetry main --squash
```

**Push local changes back upstream** (only changes under `libs/lib-oriv-telemetry/`):

```bash
git subtree push --prefix=libs/lib-oriv-telemetry lib-oriv-telemetry main
```

Then install in editable mode from the host project:

```bash
uv add --editable ./libs/lib-oriv-telemetry
```

---

## Quick start

### Logger

```python
from lib_oriv_telemetry import (
    EnvironmentEnum,
    LoggerOverrides,
    OTELFormatter,
    create_logger,
)

logger = create_logger(
    name="my_service",
    environment=EnvironmentEnum.PRODUCTION,
    formatter=OTELFormatter(),              # injects trace_id / span_id
    log_file_path="./logs",                 # optional rotating file
    overrides=LoggerOverrides(
        override_loggers={"my_dependency"},  # silence/reroute extras
    ),
)

logger.info("service started")
```

### Telemetry (tracing + metrics + logs)

```python
from lib_oriv_telemetry import EnvironmentEnum, Telemetry

telemetry = Telemetry(
    service_name="my-service",
    service_version="1.4.0",
    environment=EnvironmentEnum.PRODUCTION,
    trace_endpoint="http://otel-collector:4317",
    metric_endpoint="http://otel-collector:4317",
    log_endpoint="http://otel-collector:4317",
    headers={"x-api-key": "..."},
    trace_llm_metrics=True,   # auto-instruments LiteLLM and DSPy if installed
)

@telemetry.trace_method
async def handle_request(request_id: str) -> None:
    ...

# Or as an async context manager with header-based context propagation:
async with telemetry.trace_context(
    span_name="process_payload",
    headers=incoming_request_headers,
    attributes={"payload.size": 1024},
):
    ...
```

`Telemetry` is a process-wide singleton — subsequent constructor calls return the original instance.

### Model observability

Instrument any model call (LLM, OCR, embeddings) with provider-agnostic metrics:

```python
from lib_oriv_telemetry import ModelObservability
from lib_oriv_telemetry.instrumentation.dspy import DSPyPredictionUsagePlugin

observability = ModelObservability(plugin=DSPyPredictionUsagePlugin())

async with observability.observe(extra_attributes={"tenant": "acme"}) as submit:
    prediction = await my_dspy_program(question="...")
    submit(prediction)        # captures usage; metrics emitted on context exit
```

For Mistral OCR:

```python
from lib_oriv_telemetry.instrumentation.mistralai import OCRUsagePlugin

ocr_obs = ModelObservability(plugin=OCRUsagePlugin())

async with ocr_obs.observe() as submit:
    response = await mistral_client.ocr.process(...)
    submit(response)
```

### Custom usage plugin

Implement `UsagePlugin[T]` to instrument any other provider:

```python
from typing import Any, Dict, Tuple
from lib_oriv_telemetry import UsagePlugin

class MyEmbeddingsPlugin(UsagePlugin[MyEmbeddingsResponse]):
    name = "embeddings"

    @property
    def metric_definitions(self) -> Dict[str, str]:
        return {"embedding_tokens_total": "Total embedding tokens"}

    @property
    def counter_metric_definitions(self) -> Dict[str, str]:
        return self.metric_definitions

    @property
    def histogram_metric_definitions(self) -> Dict[str, str]:
        return self.metric_definitions

    def extract_metrics(self, usage) -> Dict[str, float]:
        return {"embedding_tokens_total": usage.token_count}

    def span_attributes(self, usage) -> Dict[str, Any]:
        return {"embeddings.tokens": usage.token_count}

    def get_model_details(self, usage) -> Tuple[str, str]:
        return "my-provider", usage.model_id
```

---

## Public API

```python
from lib_oriv_telemetry import (
    # logging
    create_logger,
    ensure_logger,
    setup_logger,
    LoggerOverrides,
    OTELFormatter,
    # tracing
    Telemetry,
    LLMUsageSpanProcessor,
    # metrics
    ModelObservability,
    ObservabilityRecord,
    UsagePlugin,
    # shared
    EnvironmentEnum,
)
```

Optional-extras plugins must be imported from their submodules:

```python
from lib_oriv_telemetry.instrumentation.dspy import DSPyPredictionUsagePlugin
from lib_oriv_telemetry.instrumentation.mistralai import OCRUsagePlugin
```

---

## Development

```bash
uv sync                    # install runtime + dev deps
uv run pytest tests/       # run the smoke test suite
```

Requires Python ≥ 3.14.
