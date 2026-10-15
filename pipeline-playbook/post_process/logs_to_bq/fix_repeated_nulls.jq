# BigQuery rejects explicit JSON `null` for REPEATED fields ("Only optional
# fields can be set to NULL") both as the field's whole value and as any
# element inside the array (e.g. "airline_iata":[null], from a known
# TWJF bug wrapping an unset scalar into a single-element list - see
# trajectory-worker-job-factory/lib/services.py, "resuming progress from a
# previous job"). Bare null -> []; null elements inside an array are dropped.
def fix_null_repeated(f):
  if (.jsonPayload | has(f))
  then
    if (.jsonPayload[f] == null)
    then .jsonPayload[f] = []
    elif ((.jsonPayload[f] | type) == "array")
    then .jsonPayload[f] |= map(select(. != null))
    else . end
  else . end;

# jsonPayload.twjd.flight_id is REPEATED too (unlike top-level jsonPayload.flight_id,
# which is NULLABLE), so it needs the same treatment nested one level down.
def fix_null_repeated_twjd(f):
  if (.jsonPayload.twjd != null) and (.jsonPayload.twjd | has(f)) and (.jsonPayload.twjd[f] == null)
  then .jsonPayload.twjd[f] = []
  else . end;

(reduce ["airline_iata", "arrival_airport_icao", "departure_airport_icao", "callsign", "flight_number", "reason"][] as $f
  (.; fix_null_repeated($f)))
| fix_null_repeated_twjd("flight_id")
