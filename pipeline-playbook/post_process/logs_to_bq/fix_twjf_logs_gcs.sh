#!/usr/bin/env bash
set -euo pipefail

# Reads every .json log file under a source GCS path, pipes it through
# fix_repeated_nulls.jq (fixes REPEATED-field nulls that break `bq load`,
# e.g. "airline_iata":null or "airline_iata":[null]), and writes the
# corrected copy to a destination GCS path, preserving the relative
# directory structure.
# -
# NOTE: run this from Cloud Shell or a GCE VM in the same region as the
# bucket (us-east1), not a local laptop - each file is read down and
# written back up, and that's fast/free inside GCP but a full
# download+upload over the public internet from a home/office connection.
#
# Usage:
#   ./fix_twjf_logs_gcs.sh gs://bucket/path/to/twjf-logs gs://bucket/path/to/twjf-logs-fixed
#
# Optional: set PARALLEL_JOBS to process multiple files concurrently
# (default 1, i.e. sequential).

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <src-gcs-prefix> <dest-gcs-prefix>" >&2
  exit 1
fi

SRC_PREFIX="${1%/}"
DEST_PREFIX="${2%/}"
PARALLEL_JOBS="${PARALLEL_JOBS:-1}"
JQ_FILTER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/fix_repeated_nulls.jq"

fix_one_file() {
  local src="$1"
  local rel="${src#"$SRC_PREFIX"/}"
  local dest="$DEST_PREFIX/$rel"
  echo "fixing: $src -> $dest"
  gsutil cat "$src" | jq -c -f "$JQ_FILTER" | gsutil cp - "$dest"
}
export -f fix_one_file
export SRC_PREFIX DEST_PREFIX JQ_FILTER

gsutil ls -r "$SRC_PREFIX/*" | grep '\.json$' | tr '\n' '\0' \
  | xargs -0 -n1 -P "$PARALLEL_JOBS" -I{} bash -c 'fix_one_file "$@"' _ {}

echo "done: fixed copies written under $DEST_PREFIX"
