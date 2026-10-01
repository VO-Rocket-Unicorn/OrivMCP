// Package schemas holds the shapes this server reads from ODAS and returns
// from its tools.
//
// Decoding validates as well as parses. Required fields must be present,
// enum values must be known, a field may be read under several names (the
// first one present wins), and null is refused wherever the field is not
// nullable. Any violation makes the whole response malformed.
package schemas

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"reflect"
	"strings"
)

var jsonNull = []byte("null")

// object is one JSON object being decoded into a struct.
type object struct {
	name   string
	fields map[string]json.RawMessage
	errs   []error
}

func newObject(name string, data []byte) (*object, error) {
	var fields map[string]json.RawMessage
	if bytes.Equal(bytes.TrimSpace(data), jsonNull) {
		return nil, fmt.Errorf("%s: input should be an object, got null", name)
	}
	if err := json.Unmarshal(data, &fields); err != nil {
		return nil, fmt.Errorf("%s: input should be an object: %w", name, err)
	}
	return &object{name: name, fields: fields}, nil
}

// lookup returns the first of keys present in the object.
func (o *object) lookup(keys []string) (json.RawMessage, string, bool) {
	for _, key := range keys {
		if raw, ok := o.fields[key]; ok {
			return raw, key, true
		}
	}
	return nil, "", false
}

func (o *object) err() error {
	return errors.Join(o.errs...)
}

// required decodes the first present key into dst, failing when none is present.
func required[T any](o *object, dst *T, keys ...string) {
	raw, key, ok := o.lookup(keys)
	if !ok {
		o.errs = append(o.errs, fmt.Errorf("%s.%s: field required", o.name, strings.Join(keys, "|")))
		return
	}
	decodeInto(o, raw, key, dst)
}

// optional decodes the first present key into dst, keeping dst's current
// value (the default) when none is present.
func optional[T any](o *object, dst *T, keys ...string) {
	if raw, key, ok := o.lookup(keys); ok {
		decodeInto(o, raw, key, dst)
	}
}

func decodeInto[T any](o *object, raw json.RawMessage, key string, dst *T) {
	if bytes.Equal(bytes.TrimSpace(raw), jsonNull) {
		if reflect.TypeFor[T]().Kind() != reflect.Pointer {
			o.errs = append(o.errs, fmt.Errorf("%s.%s: input should not be null", o.name, key))
		}
		var zero T
		*dst = zero
		return
	}
	var value T
	if err := json.Unmarshal(raw, &value); err != nil {
		o.errs = append(o.errs, fmt.Errorf("%s.%s: %w", o.name, key, err))
		return
	}
	*dst = value
}

// orEmpty returns s, or an empty (not nil) slice, so it marshals as [].
func orEmpty[T any](s []T) []T {
	if s == nil {
		return []T{}
	}
	return s
}

// enum is a closed set of string values.
type enum[T ~string] []T

func (e enum[T]) decode(data []byte, dst *T, typeName string) error {
	var s string
	if err := json.Unmarshal(data, &s); err != nil {
		return fmt.Errorf("%s: input should be a string: %w", typeName, err)
	}
	for _, value := range e {
		if string(value) == s {
			*dst = value
			return nil
		}
	}
	return fmt.Errorf("%s: input should be one of %v, got %q", typeName, e.strings(), s)
}

func (e enum[T]) strings() []string {
	out := make([]string, len(e))
	for i, value := range e {
		out[i] = string(value)
	}
	return out
}

// Values returns the enum's values as []any, as a JSON schema enum wants.
func (e enum[T]) Values() []any {
	out := make([]any, len(e))
	for i, value := range e {
		out[i] = string(value)
	}
	return out
}
