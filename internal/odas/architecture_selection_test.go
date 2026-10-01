package odas

import (
	"context"
	"testing"
	"time"
)

func TestResolveArchitectureEmptyLeaves(t *testing.T) {
	stub := &odasStub{status: 200, body: `{"payload":{"taxonomyid":"tx","taxonomy_version":"1","device_class":"ADC","leaves":[]}}`}
	srv := stub.serve(t)
	client := NewArchitectureSelectionClient(NewHTTPClient(2*time.Second, 4), discard, ArchitectureSelectionURLs{
		DecisionTreesURL: srv.URL + "/api/v1/decision-trees",
		TaxonomiesURL:    srv.URL + "/api/v1/taxonomies",
	})
	_, err := client.ResolveArchitecture(context.Background(), NewSecret("t"), "adc.sar", "SAR ADC")
	if got, want := toolMessage(t, err), "No architecture resolved for 'SAR ADC' under device class 'adc.sar'."; got != want {
		t.Errorf("message = %q, want %q", got, want)
	}
	if got := stub.last.URL.EscapedPath() + "?" + stub.last.URL.RawQuery; got != "/api/v1/taxonomies/adc.sar?architecture_name=SAR+ADC" {
		t.Errorf("request = %s", got)
	}
}

func TestDecisionTreeNodeURL(t *testing.T) {
	stub := &odasStub{status: 200, body: `{"payload":{"node":{"id":"q1","question":"?","evidence_type":"e"}}}`}
	srv := stub.serve(t)
	client := NewArchitectureSelectionClient(NewHTTPClient(2*time.Second, 4), discard, ArchitectureSelectionURLs{
		DecisionTreesURL: srv.URL + "/api/v1/decision-trees",
	})
	node, err := client.GetDecisionTreeNode(context.Background(), NewSecret("t"), "adc:sar", "zz top")
	if err != nil {
		t.Fatal(err)
	}
	if node.ID != "q1" || node.Answers == nil || node.RecognitionTriggers == nil {
		t.Errorf("node = %+v", node)
	}
	if got := stub.last.URL.EscapedPath() + "?" + stub.last.URL.RawQuery; got != "/api/v1/decision-trees/adc:sar/nodes/zz%20top?by=ai" {
		t.Errorf("request = %s", got)
	}
}
