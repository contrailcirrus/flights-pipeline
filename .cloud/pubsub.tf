resource "google_pubsub_topic" "spire_ingest_api_scraper_egress" {
  name = "spire-ingest-api-scraper-egress-dev"
}

resource "google_pubsub_subscription" "spire_ingest_resample_worker_ingress" {
  name  = "spire-ingest-resample-worker-ingress-dev"
  topic = google_pubsub_topic.spire_ingest_api_scraper_egress.id

  ack_deadline_seconds         = 600
  retain_acked_messages        = true
  enable_exactly_once_delivery = true
  enable_message_ordering      = true

  retry_policy {
    minimum_backoff = "30s"
    maximum_backoff = "60s"
  }
}
