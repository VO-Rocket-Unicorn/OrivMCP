package schemas

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestDeviceClassNodeAliasesAndRequired(t *testing.T) {
	var n DeviceClassNode
	if err := json.Unmarshal([]byte(`{"id":"a","name":"A","description":"d","child_count":2,"path":["a"]}`), &n); err != nil {
		t.Fatal(err)
	}
	if n.ChildCount != 2 {
		t.Errorf("child_count alias not read: %+v", n)
	}
	err := json.Unmarshal([]byte(`{"id":"a","name":"A","description":"d","path":["a"]}`), &n)
	if err == nil || !strings.Contains(err.Error(), "childCount|child_count: field required") {
		t.Errorf("missing childCount error = %v", err)
	}
	err = json.Unmarshal([]byte(`{"id":"a","name":"A","description":"d","childCount":1,"path":null}`), &n)
	if err == nil || !strings.Contains(err.Error(), "should not be null") {
		t.Errorf("null path error = %v", err)
	}
}

func TestOdasRowAliasPrecedenceAndEnums(t *testing.T) {
	var r OdasRequirementRow
	raw := `{"requirementId":"rid","id":"other","name":"N","statement":"s","description":"d",
		"level":"SYSTEM","type":"FUNCTIONAL","isAtomic":true,"is_atomic":false,"altitude":"atomic","childCount":0}`
	if err := json.Unmarshal([]byte(raw), &r); err != nil {
		t.Fatal(err)
	}
	if r.ID != "rid" || r.Statement != "s" || !r.IsAtomic {
		t.Errorf("first alias must win: %+v", r)
	}
	if r.Path == nil {
		t.Error("absent path must default to []")
	}

	bad := strings.Replace(raw, `"altitude":"atomic"`, `"altitude":"galactic"`, 1)
	if err := json.Unmarshal([]byte(bad), &r); err == nil || !strings.Contains(err.Error(), "Altitude") {
		t.Errorf("bad enum error = %v", err)
	}
}

func TestOutputsMarshalListsAsArrays(t *testing.T) {
	out, _ := json.Marshal(ListDeviceClassesOutput{Nodes: orEmpty[DeviceClassNode](nil)})
	if string(out) != `{"nodes":[],"nextCursor":null}` {
		t.Errorf("marshal = %s", out)
	}
	node, _ := json.Marshal(RequirementNode{})
	if !strings.Contains(string(node), `"path":null`) || !strings.Contains(string(node), `"isAtomic":false`) {
		t.Errorf("requirement node = %s", node)
	}
}

func TestDecisionTreeRequiresNodes(t *testing.T) {
	var tree DecisionTree
	err := json.Unmarshal([]byte(`{"tree_id":"t","version":"1","taxonomy_ref":"x","taxonomy_version":"1","root_question_id":"q1"}`), &tree)
	if err == nil || !strings.Contains(err.Error(), "nodes: field required") {
		t.Errorf("error = %v", err)
	}
}
