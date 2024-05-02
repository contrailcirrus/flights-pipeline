"""
A script to verify if a target aircraft icao code is recognized by the BADA3 dataset.
Retrieves the default/defined engine specs for the specified aircraft.
"""

from pycontrails_bada.bada3 import BADA3
import json

# gcloud storage cp --quiet --recursive --no-clobber gs://contrails-301217-bada/bada/bada3 .
BADA3_FP = "bada3"

bada = BADA3(bada_path=BADA3_FP)

if __name__ == "__main__":
    aircraft_type_icao = "E295"  # in bada3
    # aircraft_type_icao = 'EC20'  # not in bada3

if bada.check_aircraft_type_availability(aircraft_type_icao, raise_error=False):
    print(f"{aircraft_type_icao} found in BADA")

    print("fetching engine specs...")
    engine_props = bada.get_aircraft_engine_properties(
        atyp_icao=aircraft_type_icao,
    )
    print(json.dumps(engine_props.__dict__, indent=4))

else:
    print(f"{aircraft_type_icao} NOT found in BADA")
