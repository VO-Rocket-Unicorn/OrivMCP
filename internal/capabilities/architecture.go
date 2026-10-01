package capabilities

import (
	"context"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/odas"
	"github.com/VO-Rocket-Unicorn/OrivMCP/internal/schemas"
)

const (
	deviceClassKeyDescription = "Device class key identifying the decision tree / taxonomy (e.g. 'adc.sar')."
	rootNodeID                = "root"
)

type getDecisionTreeInput struct {
	DeviceClassKey string `json:"device_class_key"`
}

type getDecisionTreeNodeInput struct {
	DeviceClassKey string `json:"device_class_key"`
	NodeID         string `json:"node_id,omitempty"`
}

type resolveArchitectureInput struct {
	DeviceClassKey   string `json:"device_class_key"`
	ArchitectureName string `json:"architecture_name"`
}

func registerArchitectureTools(server *registrar, client *odas.ArchitectureSelectionClient) {
	meta := func() mcp.Meta { return tagsMeta(ArchitectureTag) }

	addTool(server, toolDef{
		name: "get_decision_tree",
		description: "Fetch the FULL AI decision tree for a device class in one call — every question " +
			"node keyed by id, plus root_question_id to start from. Walk it YOURSELF in memory, " +
			"one question at a time: start at nodes[root_question_id], ask its `question`, " +
			"match the reply to one answer's `value`, then move to nodes[that answer's `next`] " +
			"and repeat. When an answer's `next` is null, you've reached a leaf — call " +
			"resolve_architecture with that answer's `resolves_toward` to get the final " +
			"architecture. Prefer get_decision_tree_node instead if you'd rather fetch one " +
			"question at a time than hold the whole tree yourself.",
		meta: meta(),
		input: inputSchema[getDecisionTreeInput](map[string]arg{
			"device_class_key": {description: deviceClassKeyDescription},
		}),
	}, func(ctx context.Context, req *mcp.CallToolRequest, in getDecisionTreeInput) (schemas.DecisionTree, error) {
		token, err := odasToken(req)
		if err != nil {
			return schemas.DecisionTree{}, err
		}
		return client.GetDecisionTree(ctx, token, in.DeviceClassKey)
	})

	addTool(server, toolDef{
		name: "get_decision_tree_node",
		description: "Fetch ONE question node of a device class's AI decision tree — call-per-question, " +
			"instead of the whole tree. Call with node_id='root' to get the first question; " +
			"answer it, then call again with that answer's `next` as node_id to get the " +
			"following question, and repeat. When an answer's `next` is null, you've reached a " +
			"leaf — call resolve_architecture with that answer's `resolves_toward` to get the " +
			"final architecture. Do NOT call get_decision_tree first; this walks the tree on " +
			"its own, one node per call.",
		meta: meta(),
		input: inputSchema[getDecisionTreeNodeInput](map[string]arg{
			"device_class_key": {description: deviceClassKeyDescription},
			"node_id": {
				description: "'root' to start the walk, or a previous answer's `next` value to continue it.",
				def:         rootNodeID,
			},
		}),
	}, func(ctx context.Context, req *mcp.CallToolRequest, in getDecisionTreeNodeInput) (schemas.DecisionNode, error) {
		token, err := odasToken(req)
		if err != nil {
			return schemas.DecisionNode{}, err
		}
		return client.GetDecisionTreeNode(ctx, token, in.DeviceClassKey, in.NodeID)
	})

	addTool(server, toolDef{
		name: "resolve_architecture",
		description: "Resolve a decision-tree leaf's `resolves_toward` value to its full architecture " +
			"record. Call this once get_decision_tree's walk reaches a leaf (an answer whose " +
			"`next` is null) — architecture_name is that answer's `resolves_toward`.",
		meta: meta(),
		input: inputSchema[resolveArchitectureInput](map[string]arg{
			"device_class_key": {description: deviceClassKeyDescription},
			"architecture_name": {
				description: "The `resolves_toward` value from the leaf answer reached while walking the decision tree.",
			},
		}),
	}, func(ctx context.Context, req *mcp.CallToolRequest, in resolveArchitectureInput) (schemas.ArchitectureDetail, error) {
		token, err := odasToken(req)
		if err != nil {
			return schemas.ArchitectureDetail{}, err
		}
		return client.ResolveArchitecture(ctx, token, in.DeviceClassKey, in.ArchitectureName)
	})
}
