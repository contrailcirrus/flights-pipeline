# --------------
# TOPICS
# --------------

resource "google_pubsub_topic" "prod_api_scraper_egress" {
  name = "prod-fp-api-scraper-egress"
}


# --------------
# SUBSCRIPTIONS
# --------------

resource "google_pubsub_subscription" "prod_resample_worker_ingress" {
  name  = "prod-fp-resample-worker-ingress"
  topic = google_pubsub_topic.prod_api_scraper_egress.id

  ack_deadline_seconds         = 300
  enable_message_ordering      = true
  enable_exactly_once_delivery = true
  message_retention_duration = "302400s"  # 3.5 day


  retry_policy {
    minimum_backoff = "1s"
    maximum_backoff = "4s"
  }

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.prod_api_scraper_egress,
  ]
}
