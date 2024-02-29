# Spire Ingest Job Publisher
A CloudFunction that builds a "spire inject job" payload, 
and publishes the job to an ordered pubsub topic.

The service is triggered periodically by a cron.

The [Spire Ingest API Scraper](../spire-ingest-api-scraper) service dequeues the jobs, 
in order, and scrapes flight waypoint observation data the Spire API.

If the downstream consumer service fails, jobs will remain queued, in order, 
and contiguous data scraping will resume once the service is restored.

> Note: Google CloudFunctions do not support pipenv and Pipfile for dependency management.
> As such, this service diverges from internal practices, and uses a requirements.txt
