from typing import List, Dict
from typing_extensions import TypedDict
from datetime import datetime, date

from data import flight_1, flight_2, flight_3

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


def query(airline: str, flight_number: str, date: date) -> List[ResponseObject]:
    response_data: List[ResponseObject] = []

    if flight_number == "0":
        response_data = []
    elif flight_number == "1":
        response_data = [
            {
                **flight_1,
                "airline_iata": airline,
                "flight_number": flight_number,
            }
        ]
        print(response_data)
    elif flight_number == "2":
        response_data = [
            {
                **flight_2,
                "airline_iata": airline,
                "flight_number": flight_number,
            }
        ]
    elif flight_number == "3":
        response_data = [
            {
                **flight_1,
                "airline_iata": airline,
                "flight_number": flight_number,
            },
            {
                **flight_2,
                "airline_iata": airline,
                "flight_number": flight_number,
            },
            {
                **flight_3,
                "airline_iata": airline,
                "flight_number": flight_number,
            },
        ]
    else:
        response_data = [
            {
                **flight_3,
                "airline_iata": airline,
                "flight_number": flight_number,
            }
        ]
    return response_data
