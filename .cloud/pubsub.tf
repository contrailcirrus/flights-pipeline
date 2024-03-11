resource "google_pubsub_topic" "spire_ingest_api_scraper_egress_dev" {
  name = "spire-ingest-api-scraper-egress-dev"
}

resource "google_pubsub_topic" "spire_ingest_api_scraper_egress_prod" {
  name = "spire-ingest-api-scraper-egress-prod"
}

resource "google_pubsub_subscription" "spire_ingest_resample_worker_ingress_dev" {
  name  = "spire-ingest-resample-worker-ingress-dev"
  topic = google_pubsub_topic.spire_ingest_api_scraper_egress_dev.id

  ack_deadline_seconds         = 600
  enable_message_ordering      = true
  message_retention_duration = "86400s"  # 1 day

  retry_policy {
    minimum_backoff = "30s"
    maximum_backoff = "60s"
  }
}

resource "google_pubsub_subscription" "spire_ingest_resample_worker_ingress_prod" {
  name  = "spire-ingest-resample-worker-ingress-prod"
  topic = google_pubsub_topic.spire_ingest_api_scraper_egress_prod.id

  ack_deadline_seconds         = 600
  enable_message_ordering      = true
  message_retention_duration = "302400s"  # 3.5 day


  retry_policy {
    minimum_backoff = "30s"
    maximum_backoff = "60s"
  }
}