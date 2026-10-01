package capabilities

import (
	"encoding/json"
	"testing"
)

func listValidator() *argsValidator {
	return newArgsValidator("list_device_classes", inputSchema[listDeviceClassesInput](map[string]arg{
		"parent_id": {nullable: true},
		"depth":     {def: 1, minimum: new(float64(1)), maximum: new(float64(3))},
		"cursor":    {nullable: true},
	}))
}

func TestValidateAppliesDefaultsAndCoerces(t *testing.T) {
	v := listValidator()
	out, problem := v.validate(json.RawMessage(`{"depth":"2","extra":"ignored"}`))
	if problem != "" {
		t.Fatal(problem)
	}
	var in listDeviceClassesInput
	if err := json.Unmarshal(out, &in); err != nil {
		t.Fatal(err)
	}
	if in.Depth != 2 || in.ParentID != nil {
		t.Errorf("input = %+v", in)
	}

	out, problem = v.validate(nil)
	if problem != "" {
		t.Fatal(problem)
	}
	_ = json.Unmarshal(out, &in)
	if in.Depth != 1 {
		t.Errorf("default depth = %d", in.Depth)
	}
}

func TestValidateMessagesMatchPydantic(t *testing.T) {
	v := listValidator()
	cases := map[string]string{
		`{"depth":5}`:   "1 validation error for list_device_classesArguments\ndepth\n  Input should be less than or equal to 3",
		`{"depth":0}`:   "1 validation error for list_device_classesArguments\ndepth\n  Input should be greater than or equal to 1",
		`{"depth":1.5}`: "1 validation error for list_device_classesArguments\ndepth\n  Input should be a valid integer, got a number with a fractional part",
		`{"depth":"x"}`: "1 validation error for list_device_classesArguments\ndepth\n  Input should be a valid integer, unable to parse string as an integer",
		`{"depth":null,"parent_id":3}`: "2 validation errors for list_device_classesArguments\n" +
			"parent_id\n  Input should be a valid string\ndepth\n  Input should be a valid integer",
	}
	for args, want := range cases {
		if _, got := v.validate(json.RawMessage(args)); got != want {
			t.Errorf("validate(%s) =\n%q\nwant\n%q", args, got, want)
		}
	}
}

func TestValidateEnumAndRequired(t *testing.T) {
	v := newArgsValidator("requirement_tree_search", inputSchema[requirementTreeSearchInput](map[string]arg{
		"query":            {minLength: new(1)},
		"forChildAltitude": forChildAltitudeArg,
		"type":             {nullable: true},
		"excludeId":        excludeIDArg,
		"inSubtreeOf":      inSubtreeOfArg,
		"page":             pageArg,
		"limit":            limitArg,
	}))
	cases := map[string]string{
		`{}`:           "1 validation error for requirement_tree_searchArguments\nquery\n  Field required",
		`{"query":""}`: "1 validation error for requirement_tree_searchArguments\nquery\n  String should have at least 1 character",
		`{"query":"x","forChildAltitude":"unknown"}`: "1 validation error for requirement_tree_searchArguments\nforChildAltitude\n  Input should be 'stakeholder', 'system' or 'atomic'",
	}
	for args, want := range cases {
		if _, got := v.validate(json.RawMessage(args)); got != want {
			t.Errorf("validate(%s) =\n%q\nwant\n%q", args, got, want)
		}
	}
	if _, problem := v.validate(json.RawMessage(`{"query":"x","forChildAltitude":null,"type":"FUNCTIONAL"}`)); problem != "" {
		t.Errorf("valid args rejected: %s", problem)
	}
}
