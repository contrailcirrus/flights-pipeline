#!/usr/bin/env bash

set -e

YESTERDAY="$(date -d "2 days ago" -u +%Y-%m-%dT%H)"

curl -f "https://api.contrails.org/v1/adsb/telemetry?date=$YESTERDAY" -H "x-api-key: $CONTRAILS_API_KEY" >> /dev/null

echo "Successfully called API for $YESTERDAY"
