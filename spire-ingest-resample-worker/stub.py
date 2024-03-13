pubsub_message = b'{"flight_info": {"icao_address": "4B0293", "flight_id": "ef9fb457-0f70-4780-9154-6a5362e39862", "callsign": "SWR64C", "tail_number": "HB-AZJ", "flight_number": "LX644", "aircraft_type_icao": "E295", "airline_iata": "LX", "departure_airport_icao": "LSZH", "departure_scheduled_time": "2024-03-01T16:25:00Z", "arrival_airport_icao": "LFPG", "arrival_scheduled_time": "2024-03-01T17:40:00Z"}, "records": [{"timestamp": "2024-03-01T16:37:54Z", "latitude": 47.453758, "longitude": 8.555093, "altitude_baro": 36430, "flight_level": null, "imputed": false}, {"timestamp": "2024-03-01T16:38:02Z", "latitude": 47.454254, "longitude": 8.574745, "altitude_baro": 36480, "flight_level": null, "imputed": false}, {"timestamp": "2024-03-01T16:38:53Z", "latitude": 47.455032, "longitude": 8.658332, "altitude_baro": 36420, "flight_level": null, "imputed": false}, {"timestamp": "2024-03-01T16:39:53Z", "latitude": 47.455627, "longitude": 8.743688, "altitude_baro": 36400, "flight_level": null, "imputed": false}, {"timestamp": "2024-03-01T16:41:02Z", "latitude": 47.455795, "longitude": 8.867047, "altitude_baro": 36430, "flight_level": null, "imputed": false}, {"timestamp": "2024-03-01T16:41:45Z", "latitude": 47.45573, "longitude": 8.947877, "altitude_baro": 36510, "flight_level": null, "imputed": false}]}'

redis_response = {
    b"w1_flight_id": b"\xef\x9f\xb4W\x0fpG\x80\x91TjSb\xe3\x98b",
    b"w1_latitude": b"37.333333",
    b"w1_longitude": b"-7.001100",
    b"w1_altitude_ft": b"32120",
    b"w1_timestamp": b"1709305380",
}

pubsub_bq_out = b'{"timestamp": "2024-03-13T09:24:41Z", "latlon": "{"type": "Point", "coordinates": [-119.3, 33.4]}", "altitude_baro": 36344, "flight_level": 360, "imputed": true, "icao_address": "foo4bar", "flight_id": "3333-abss-2112..."}'
