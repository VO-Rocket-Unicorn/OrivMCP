package schemas

// InventoryOutput backs the flight_inventory demo resource.
type InventoryOutput struct {
	Flights []string `json:"flights"`
}
