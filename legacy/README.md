# OrivMCP — legacy Python implementation

This is the original Python implementation of OrivMCP. It was superseded by the
Go implementation at the repository root and is kept here for reference only.
Nothing builds, tests or deploys it any more.

To run it anyway, from this directory:

```bash
uv sync --locked
cp ../.env.example .env   # settings are read from .env in the working directory
uv run app
```

`deps/lib-oriv-telemetry` is the git subtree of the shared telemetry library this
implementation used. Its subtree prefix is now `legacy/deps/lib-oriv-telemetry`.
