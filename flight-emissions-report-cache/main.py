from flask import Request, jsonify, Response
import functions_framework
from typing import List, Dict, Tuple
from typing_extensions import TypedDict
from datetime import datetime

EXAMPLE_FLIGHT_ID = "7094901859951170919"


class ResponseObject(TypedDict):
    airline: str
    destination: str
    flightNumber: str
    id: str
    origin: str
    severity: str
    tons: int
    unixTime: int


ErrorResponse = Dict[str, str]

AIRLINES = [
    "klm",  # {"airline": "KL"},
    "tui",  # {"airline": "BY"},
    "transavia",  # {"airline": "HV"},
    "american airlines",  # {"airline": "AA"},
    "united airlines",  # {"airline": "UA"},
    "delta airlines",  # {"airline": "DL"},
    "virgin atlantic",  # {"airline": "VS"},
    "southwest airlines",  # {"airline": "WN"},
    "alaska airlines",  # {"airline": "AS"},
    "swiss airlines",  # {"airline": "LX"},
    "british airways",  # {"airline": "BA"},
    "air france",  # {"airline": "AF"},
    "dhl",  # {"airline": "D0"},
    "discover airlines",  # {"icao_address": "3C6565"},  # iagos tail_number: "D-AIKE"
    "cathay pacific",  # {"icao_address": "780192"},  # iagos tail_number: "B-HLR"
    "china airlines",  # {"icao_address": "8991BD"},  # iagos tail_number: "B-18316", # {"icao_address": "8991BE"},  # iagos tail_number: "B-18317"
    "hawaiian airlines",  # {"icao_address": "A46AD6"},  # iagos tail_number: "N384HA"
    "air france",  # {"icao_address": "39644E"},  # iagos tail_number: "F-GZCO"
    "lufthansa",  # {"icao_address": "3C64F4"},  # iagos tail_number: "D-AIGT"
    "iberia",  # {"icao_address": "3455C1"},  # iagos tail_number: "EC-MSY", # {"icao_address": "3C656F"},  # iagos tail_number: "D-AIKO"
    "air canada",  # {"icao_address": "C04FBB"},  # iagos tail_number: "C-GEFA"
]


@functions_framework.http
def handler(req: Request) -> Tuple[Response, int, Dict[str, str]]:
    # Set CORS headers for the preflight request
    if req.method == "OPTIONS":
        # Allows GET requests from any origin with the Content-Type
        # header and caches preflight response for an 3600s
        headers = {
            "Access-Control-Allow-Origin": "http://localhost:5173/",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
        }

        return (jsonify([]), 204, headers)

    # Set CORS headers for the main request
    headers = {"Access-Control-Allow-Origin": "*"}

    try:
        query_params = req.args
        airline = query_params.get("airline")
        date_str = query_params.get("date")
        flight_number = query_params.get("flightNumber")

        if not airline or not date_str or not flight_number:
            missing = []

            if not airline:
                missing.append("airline")
            if not date_str:
                missing.append("date")
            if not flight_number:
                missing.append("flightNumber")

            raise ValueError(f"Missing required query parameters: {missing}")

        if airline and airline.lower() not in AIRLINES:
            raise ValueError(f"Invalid airline: {airline}")

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(
                f"Invalid date format: {date_str}. Expected format: YYYY-MM-DD"
            )

        today = datetime.today().date()
        if date_obj > today:
            raise ValueError("The date cannot be in the future")

        # Convert date_obj to a datetime object at midnight
        datetime_obj = datetime.combine(date_obj, datetime.min.time())
        # multiply by 1000 to conform with dayjs date format
        unix_time = int(datetime_obj.timestamp()) * 1000

        response_data: List[ResponseObject] = []
        if flight_number == "0":
            response_data = []
        elif flight_number == "1":
            response_data = [
                {
                    "airline": airline,
                    "destination": "Newark",
                    "flightNumber": flight_number,
                    "id": EXAMPLE_FLIGHT_ID,
                    "origin": "Reykjavik",
                    "severity": "moderate",
                    "tons": 0,
                    "unixTime": unix_time,
                }
            ]
            print(response_data)
        elif flight_number == "2":
            response_data = [
                {
                    "airline": airline,
                    "destination": "JFK",
                    "flightNumber": flight_number,
                    "id": EXAMPLE_FLIGHT_ID,
                    "origin": "LAX",
                    "severity": "moderate",
                    "tons": 200,
                    "unixTime": unix_time,
                }
            ]
        elif flight_number == "3":
            response_data = [
                {
                    "airline": airline,
                    "destination": "JFK (moderate)",
                    "flightNumber": flight_number,
                    "id": "EXAMPLE_FLIGHT_ID + 1",
                    "origin": "LAX",
                    "severity": "moderate",
                    "tons": 200,
                    "unixTime": unix_time,
                },
                {
                    "airline": airline,
                    "destination": "Newark (high)",
                    "flightNumber": flight_number,
                    "id": "EXAMPLE_FLIGHT_ID + 2",
                    "origin": "Reykjavik",
                    "severity": "high",
                    "tons": 900,
                    "unixTime": unix_time,
                },
                {
                    "airline": airline,
                    "destination": "Newark (not warming)",
                    "flightNumber": flight_number,
                    "id": "EXAMPLE_FLIGHT_ID + 3",
                    "origin": "Reykjavik",
                    "severity": "high",
                    "tons": 0,
                    "unixTime": unix_time,
                },
            ]
        else:
            response_data = [
                {
                    "airline": airline,
                    "destination": "Newark",
                    "flightNumber": flight_number,
                    "id": EXAMPLE_FLIGHT_ID,
                    "origin": "Reykjavik",
                    "severity": "high",
                    "tons": 900,
                    "unixTime": unix_time,
                }
            ]

        return jsonify(response_data), 200, headers

    except ValueError as e:
        return jsonify({"error": str(e)}), 400, headers
    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500, headers
