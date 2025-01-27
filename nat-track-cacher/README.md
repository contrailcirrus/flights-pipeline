# NAT Track Cacher
This service is a kubernetes CronJob that runs every 5 minutes, 
fetches the latest geoJSON NAT tracks from the contrails-api NAT Track endpoint,
and pushes those data to a Big Query table.

