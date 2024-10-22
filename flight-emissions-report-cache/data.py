from typing_extensions import TypedDict

EXAMPLE_FLIGHT_ID = "7094901859951170919"

class ResponseObject(TypedDict):
    airline_iata: str
    arrival_airport_icao: str
    arrival_scheduled_time: int
    departure_airport_icao: str
    departure_scheduled_time: int
    flight_id: str
    flight_number: str
    sum_ef_mj: int
    time_end: int
    time_start: int


flight_1: ResponseObject = {
    "airline_iata": "fake airline",
    "arrival_airport_icao": "JFK",
    "arrival_scheduled_time": 1729512000,
    "departure_airport_icao": "LAX",
    "departure_scheduled_time": 1729497600,
    "flight_id": EXAMPLE_FLIGHT_ID + "1",
    "flight_number": "0",
    "sum_ef_mj": 0,
    "time_end": 1729512000,
    "time_start": 1729497600,
}
flight_2: ResponseObject = {
    "airline_iata": "fake airline",
    "arrival_airport_icao": "Newark",
    "arrival_scheduled_time": 1729533600,
    "departure_airport_icao": "Reykjavik",
    "departure_scheduled_time": 1729519200,
    "flight_id": EXAMPLE_FLIGHT_ID + "2",
    "flight_number": "0",
    "sum_ef_mj": 200,
    "time_end": 1729533600,
    "time_start": 1729519200,
}
flight_3: ResponseObject = {
    "airline_iata": "fake airline",
    "arrival_airport_icao": "Newark",
    "arrival_scheduled_time": 1729555200,
    "departure_airport_icao": "Reykjavik",
    "departure_scheduled_time": 1729540800,
    "flight_id": EXAMPLE_FLIGHT_ID + "3",
    "flight_number": "0",
    "sum_ef_mj": 900,
    "time_end": 1729555200,
    "time_start": 1729540800,
}
