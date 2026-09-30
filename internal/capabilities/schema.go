// Package capabilities defines what this server offers over MCP: its tools,
// prompts and resources.
package capabilities

import (
	"encoding/json"
	"fmt"
	"reflect"
	"slices"
	"strings"

	"github.com/google/jsonschema-go/jsonschema"

	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/schemas"
)

// enumSchemas gives each closed string set its enum, wherever it appears in
// an inferred schema.
var enumSchemas = map[reflect.Type]*jsonschema.Schema{
	reflect.TypeFor[schemas.Altitude]():         {Type: "string", Enum: schemas.Altitudes.Values()},
	reflect.TypeFor[schemas.ChildAltitude]():    {Type: "string", Enum: schemas.ChildAltitudes.Values()},
	reflect.TypeFor[schemas.RequirementLevel](): {Type: "string", Enum: schemas.RequirementLevels.Values()},
	reflect.TypeFor[schemas.RequirementType]():  {Type: "string", Enum: schemas.RequirementTypes.Values()},
}

// arg is what a tool declares about one argument beyond its Go type.
type arg struct {
	description string
	// def is the default applied when the argument is omitted. For a nullable
	// argument, leave it nil and set nullable: the default is then null.
	def       any
	nullable  bool
	minimum   *float64
	maximum   *float64
	minLength *int
}

// inferSchema builds a JSON schema for T with the enum types filled in.
func inferSchema[T any]() *jsonschema.Schema {
	schema, err := jsonschema.For[T](&jsonschema.ForOptions{TypeSchemas: enumSchemas})
	if err != nil {
		panic(fmt.Sprintf("inferring schema for %v: %v", reflect.TypeFor[T](), err))
	}
	return schema
}

// outputSchema infers T's schema as the tool publishes it. A list is only
// ever sent as an array, so only a pointer-to-slice (a field that is really
// null sometimes) stays nullable. Unknown fields are not ruled out, so adding
// an output field later does not break a client that validates against it.
func outputSchema[T any]() *jsonschema.Schema {
	schema := inferSchema[T]()
	tighten(schema, reflect.TypeFor[T]())
	return schema
}

func tighten(schema *jsonschema.Schema, t reflect.Type) {
	if schema == nil {
		return
	}
	switch t.Kind() {
	case reflect.Pointer:
		tighten(schema, t.Elem())
	case reflect.Slice:
		if slices.Contains(schema.Types, "null") {
			schema.Types, schema.Type = nil, "array"
		}
		tighten(schema.Items, t.Elem())
	case reflect.Map:
		tighten(schema.AdditionalProperties, t.Elem())
	case reflect.Struct:
		schema.AdditionalProperties = nil
		for i := range t.NumField() {
			field := t.Field(i)
			name, _, _ := strings.Cut(field.Tag.Get("json"), ",")
			if name == "" {
				name = field.Name
			}
			prop := schema.Properties[name]
			if prop == nil {
				continue
			}
			if field.Type.Kind() == reflect.Pointer && field.Type.Elem().Kind() == reflect.Slice {
				// Nullable itself; tighten only its items.
				tighten(prop.Items, field.Type.Elem().Elem())
				continue
			}
			tighten(prop, field.Type)
		}
	}
}

// inputSchema infers T's schema and applies each argument's description,
// default and bounds, so the published schema carries the same constraints
// the arguments are validated against. Extra arguments are ignored rather
// than refused, so a call carrying an argument this server does not know
// still gets an answer.
func inputSchema[T any](args map[string]arg) *jsonschema.Schema {
	schema := inferSchema[T]()
	schema.AdditionalProperties = nil
	for name, a := range args {
		prop, ok := schema.Properties[name]
		if !ok {
			panic(fmt.Sprintf("%v has no property %q", reflect.TypeFor[T](), name))
		}
		prop.Description = a.description
		prop.Minimum, prop.Maximum, prop.MinLength = a.minimum, a.maximum, a.minLength
		switch {
		case a.def != nil:
			raw, err := json.Marshal(a.def)
			if err != nil {
				panic(err)
			}
			prop.Default = raw
		case a.nullable:
			prop.Default = json.RawMessage("null")
			// A nullable enum must also admit null.
			if prop.Enum != nil {
				prop.Enum = append(append([]any{}, prop.Enum...), nil)
			}
		}
	}
	return schema
}
