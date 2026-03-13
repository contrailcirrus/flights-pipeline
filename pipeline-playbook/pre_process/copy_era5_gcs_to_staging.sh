#!/bin/bash

# Script to create and run a Google Cloud Transfer Service job to copy files
# from one GCS bucket to another, filtering by date prefixes between start and end dates.
set -e

if [ $# -ne 4 ]; then
  echo "Usage: $0 start_date end_date source_bucket sink_bucket"
  echo "Dates should be in YYYY-MM-DD format."
  echo "source_bucket and sink_bucket should be in the format gs://bucket-name"
  echo "Example: $0 2023-01-01 2023-01-31 gs://source-bucket gs://sink-bucket"
  echo "Note: The date range should not exceed 500 days due to GCS STS filter limits."
  exit 1
fi

start_date=$1
end_date=$2
source_bucket=$3
sink_bucket=$4

# Validate and convert dates to seconds since epoch
start_seconds=$(date -j -f "%Y-%m-%d" "$start_date" +%s 2>/dev/null)
end_seconds=$(date -j -f "%Y-%m-%d" "$end_date" +%s 2>/dev/null)

if [ -z "$start_seconds" ] || [ -z "$end_seconds" ]; then
  echo "Invalid date format. Use YYYY-MM-DD."
  exit 1
fi

if [ $start_seconds -gt $end_seconds ]; then
  echo "Start date must be before or equal to end date."
  exit 1
fi

num_days=$(( (end_seconds - start_seconds) / 86400 ))
if [ $num_days -gt 500 ]; then
  echo "Error: Date range includes $((num_days + 1)) days; maximum is 500."
  exit 1
fi

# Generate prefixes for each date in the range
prefixes=""

for ((i=0; i<=num_days; i++)); do
  date_str=$(date -j -f "%s" $((start_seconds + i * 86400)) +%Y%m%d)
  prefixes="${prefixes}${date_str}_pl.zarr,"
  prefixes="${prefixes}${date_str}_sl.zarr,"
done

# Remove trailing comma
prefixes=${prefixes%,}

# Create a unique job name
job_name="transfer-${start_date}-to-${end_date}-$(date +%s)"

# Create the transfer job
gcloud transfer jobs create "$source_bucket" "$sink_bucket" \
  --include-prefixes="$prefixes" \
  --name="$job_name"

echo "Transfer job '$job_name' created and started."
echo "Files with prefixes from $start_date to $end_date will be copied from $source_bucket to $sink_bucket."

# Monitor the transfer
last_echoed_gb=0
while true; do
  output=$(gcloud transfer operations list \
  --job-names="$job_name" \
  --format="json(metadata.status,metadata.counters)" \
  --limit=1)
  if [ $? -ne 0 ]; then
    echo "Error monitoring job. Retrying in 20 seconds."
    sleep 20
    continue
  fi
status=$(echo "$output" | jq -r '.[0].metadata.status')
bytes_transferred=$(echo "$output" | jq -r '.[0].metadata.counters.bytesCopiedToSink // 0')
bytes_failed=$(echo "$output" | jq -r '.[0].metadata.counters.bytesFromSourceFailed // 0')

  if [ -n "$bytes_transferred" ] && [ "$bytes_transferred" -gt 0 ]; then
    gb_transferred=$((bytes_transferred / 1000000000))
    if [ "$gb_transferred" -ge $((last_echoed_gb + 10)) ]; then
      echo "Total transferred: $gb_transferred GB"
      last_echoed_gb=$((gb_transferred / 10 * 10))
    fi
  fi

  if [ -n "$bytes_failed" ] && [ "$bytes_failed" -gt 0 ]; then
    echo "Errors detected: $bytes_failed bytes failed to transfer."
  fi

  if [ "$status" = "SUCCESS" ]; then
    echo "Transfer completed successfully."
    break
  elif [ "$status" = "ABORTED" ]; then
    echo "Transfer was aborted."
    break
  elif [ "$status" = "FAILED" ]; then
    echo "Transfer failed."
    break
  fi

  sleep 20
done