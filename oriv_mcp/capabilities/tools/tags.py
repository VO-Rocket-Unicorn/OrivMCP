"""Tags attached to tools, and the `_meta` payload that carries them.

MCP has no tag field of its own: a tool is name, description, schemas and
annotations. The SDK's `meta=` argument is passed through as the tool's
`_meta`, which is the one place a client can read free-form grouping from —
so that is where the tag lives.
"""

TAGS_META_KEY = "tags"

ONTOLOGY_TAG = "ontology"
REQUIREMENTS_TAG = "requirements"
ARCHITECTURE_TAG = "architecture"


def tags_meta(*tags: str) -> dict[str, list[str]]:
    """Build the `_meta` a tool declares its tags through."""
    return {TAGS_META_KEY: list(tags)}
