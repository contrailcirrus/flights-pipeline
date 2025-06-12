#!/usr/bin/env bash

YESTERDAY="$(date -d "yesterday" -u +%Y-%m-%dT%H)"

curl "https://api.contrails.org/"