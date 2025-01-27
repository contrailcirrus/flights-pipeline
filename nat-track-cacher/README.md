# NAT Track Cacher
This service is a kubernetes CronJob that runs every 5 minutes, 
fetches the latest geoJSON NAT tracks from the contrails-api NAT Track endpoint,
and pushes those data to a Big Query table.

## Environment Variables
The following environment variables are expected for production and development environments.

| name              |                           description                            |
|:------------------|:----------------------------------------------------------------:|
| NAT_TRACK_API_URL | contrails API fully-qualified URL for fetching NAT Track geojson |
| BQ_TABLE_ID       |        fully-qualified identifier for the target BQ table        |
| LOG_LEVEL         |            log level for service in cloud environment            |