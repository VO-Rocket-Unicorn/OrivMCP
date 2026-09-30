package capabilities

import (
	"encoding/json"
	"fmt"
	"math"
	"slices"
	"strconv"
	"strings"

	"github.com/google/jsonschema-go/jsonschema"
)

// argsValidator checks a tool's arguments against its (flat) input schema
// the way pydantic did in the Python implementation. Every violation is
// reported in one message, missing arguments get their defaults, extra
// arguments are ignored, and a whole-number string is accepted for an
// integer argument.
type argsValidator struct {
	model  string // "<tool>Arguments", as pydantic named the model
	fields []fieldSpec
}

type fieldSpec struct {
	name      string
	kind      string // "string" or "integer"
	nullable  bool
	required  bool
	def       json.RawMessage
	enum      []string
	minimum   *float64
	maximum   *float64
	minLength *int
}

func newArgsValidator(tool string, schema *jsonschema.Schema) *argsValidator {
	names := schema.PropertyOrder
	if len(names) == 0 {
		for name := range schema.Properties {
			names = append(names, name)
		}
		slices.Sort(names)
	}
	v := &argsValidator{model: tool + "Arguments"}
	for _, name := range names {
		prop := schema.Properties[name]
		spec := fieldSpec{
			name:      name,
			required:  slices.Contains(schema.Required, name),
			def:       prop.Default,
			minimum:   prop.Minimum,
			maximum:   prop.Maximum,
			minLength: prop.MinLength,
		}
		types := prop.Types
		if prop.Type != "" {
			types = []string{prop.Type}
		}
		for _, t := range types {
			if t == "null" {
				spec.nullable = true
			} else {
				spec.kind = t
			}
		}
		for _, e := range prop.Enum {
			if s, ok := e.(string); ok {
				spec.enum = append(spec.enum, s)
			} else if e == nil {
				spec.nullable = true
			}
		}
		if spec.kind != "string" && spec.kind != "integer" {
			panic(fmt.Sprintf("tool %s: argument %q has unsupported type %v", tool, name, types))
		}
		v.fields = append(v.fields, spec)
	}
	return v
}

// validate returns the arguments with defaults applied and values coerced,
// ready to decode, or a pydantic-style error message.
func (v *argsValidator) validate(raw json.RawMessage) (json.RawMessage, string) {
	args := map[string]any{}
	if len(raw) > 0 && string(raw) != "null" {
		decoder := json.NewDecoder(strings.NewReader(string(raw)))
		decoder.UseNumber()
		if err := decoder.Decode(&args); err != nil || args == nil {
			return nil, fmt.Sprintf("1 validation error for %s\n  Input should be an object", v.model)
		}
	}

	var problems []string
	for _, f := range v.fields {
		value, present := args[f.name]
		if !present {
			if f.required {
				problems = append(problems, f.name+"\n  Field required")
				continue
			}
			if f.def != nil {
				var def any
				_ = json.Unmarshal(f.def, &def)
				args[f.name] = def
			}
			continue
		}
		coerced, msg := f.check(value)
		if msg != "" {
			problems = append(problems, f.name+"\n  "+msg)
			continue
		}
		args[f.name] = coerced
	}

	if len(problems) > 0 {
		noun := "error"
		if len(problems) > 1 {
			noun = "errors"
		}
		return nil, fmt.Sprintf("%d validation %s for %s\n%s", len(problems), noun, v.model, strings.Join(problems, "\n"))
	}
	out, err := json.Marshal(args)
	if err != nil {
		return nil, err.Error()
	}
	return out, ""
}

func (f fieldSpec) check(value any) (any, string) {
	if value == nil {
		if f.nullable {
			return nil, ""
		}
		return nil, "Input should be a valid " + f.kind
	}
	switch f.kind {
	case "integer":
		n, msg := asInteger(value)
		if msg != "" {
			return nil, msg
		}
		if f.minimum != nil && float64(n) < *f.minimum {
			return nil, fmt.Sprintf("Input should be greater than or equal to %s", formatBound(*f.minimum))
		}
		if f.maximum != nil && float64(n) > *f.maximum {
			return nil, fmt.Sprintf("Input should be less than or equal to %s", formatBound(*f.maximum))
		}
		return n, ""
	default: // string
		s, ok := value.(string)
		if !ok {
			return nil, "Input should be a valid string"
		}
		if f.enum != nil && !slices.Contains(f.enum, s) {
			return nil, "Input should be " + quoteChoices(f.enum)
		}
		if f.minLength != nil && len([]rune(s)) < *f.minLength {
			unit := "character"
			if *f.minLength != 1 {
				unit = "characters"
			}
			return nil, fmt.Sprintf("String should have at least %d %s", *f.minLength, unit)
		}
		return s, ""
	}
}

// asInteger accepts a JSON integer, a whole float, or a whole-number
// string, as pydantic's lax mode does.
func asInteger(value any) (int64, string) {
	switch v := value.(type) {
	case json.Number:
		if n, err := v.Int64(); err == nil {
			return n, ""
		}
		f, err := v.Float64()
		if err != nil {
			return 0, "Input should be a valid integer"
		}
		if f != math.Trunc(f) {
			return 0, "Input should be a valid integer, got a number with a fractional part"
		}
		return int64(f), ""
	case string:
		n, err := strconv.ParseInt(strings.TrimSpace(v), 10, 64)
		if err != nil {
			return 0, "Input should be a valid integer, unable to parse string as an integer"
		}
		return n, ""
	default:
		return 0, "Input should be a valid integer"
	}
}

func formatBound(f float64) string {
	return strconv.FormatFloat(f, 'f', -1, 64)
}

// quoteChoices renders "'a', 'b' or 'c'".
func quoteChoices(values []string) string {
	quoted := make([]string, len(values))
	for i, v := range values {
		quoted[i] = "'" + v + "'"
	}
	if len(quoted) == 1 {
		return quoted[0]
	}
	return strings.Join(quoted[:len(quoted)-1], ", ") + " or " + quoted[len(quoted)-1]
}
