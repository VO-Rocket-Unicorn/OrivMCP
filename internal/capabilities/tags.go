package capabilities

import "github.com/modelcontextprotocol/go-sdk/mcp"

// Tags attached to tools, and the _meta payload that carries them.
//
// MCP has no tag field of its own: a tool is name, description, schemas and
// annotations. _meta is the one place a client can read free-form grouping
// from, so that is where the tag lives.

const (
	TagsMetaKey = "tags"

	OntologyTag     = "ontology"
	RequirementsTag = "requirements"
	ArchitectureTag = "architecture"
)

// tagsMeta builds the _meta a tool declares its tags through.
func tagsMeta(tags ...string) mcp.Meta {
	return mcp.Meta{TagsMetaKey: tags}
}
