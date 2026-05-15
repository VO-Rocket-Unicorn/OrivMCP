from pydantic import BaseModel


class SearchFlightsInput(BaseModel):
    origin: str
    destination: str
    date: str


class Flight(BaseModel):
    flight_number: str
    price: float


class SearchFlightsOutput(BaseModel):
    flights: list[Flight]


class InventoryInput(BaseModel):
    airport: str


class InventoryOutput(BaseModel):
    flights: list[str]


class PlannerInput(BaseModel):
    goal: str
