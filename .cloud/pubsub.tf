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
  enable_exactly_once_delivery = true
  message_retention_duration = "86400s"  # 1 day

  retry_policy {
    minimum_backoff = "1s"
    maximum_backoff = "4s"
  }

  dead_letter_policy {
    max_delivery_attempts = 5
    dead_letter_topic = google_pubsub_topic.spire_ingest_resample_worker_ingress_dead_letter_dev.id
  }

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.spire_ingest_api_scraper_egress_dev,
    google_pubsub_topic.spire_ingest_resample_worker_ingress_dead_letter_dev,
  ]
}

resource "google_pubsub_topic" "spire_ingest_resample_worker_ingress_dead_letter_dev" {
  name = "spire-ingest-resample-worker-ingress-dead-letter-dev"
}

resource "google_pubsub_subscription" "spire_ingest_resample_worker_ingress_dead_letter_dev" {
  name  = "spire-ingest-resample-worker-ingress-dead-letter-dev"
  topic = google_pubsub_topic.spire_ingest_resample_worker_ingress_dead_letter_dev.id
  message_retention_duration = "86400s"  # 1 day

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.spire_ingest_resample_worker_ingress_dead_letter_dev,
  ]
}

resource "google_pubsub_subscription" "spire_ingest_resample_worker_ingress_prod" {
  name  = "spire-ingest-resample-worker-ingress-prod"
  topic = google_pubsub_topic.spire_ingest_api_scraper_egress_prod.id

  ack_deadline_seconds         = 600
  enable_message_ordering      = true
  enable_exactly_once_delivery = true
  message_retention_duration = "302400s"  # 3.5 day


  retry_policy {
    minimum_backoff = "30s"
    maximum_backoff = "60s"
  }

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.spire_ingest_api_scraper_egress_prod,
  ]
}

resource "google_pubsub_topic" "spire_ingest_resample_worker_bigquery_dev" {
  name = "spire-ingest-resample-worker-bigquery-dev"
}

resource "google_pubsub_topic" "spire_ingest_resample_worker_bigquery_dead_letter_dev" {
  name = "spire-ingest-resample-worker-bigquery-dead-letter-dev"
}

resource "google_pubsub_subscription" "spire_ingest_resample_worker_bigquery_delivery_dev" {
  name  = "spire_ingest_resample_worker_bigquery_delivery_dev"
  topic = google_pubsub_topic.spire_ingest_resample_worker_bigquery_dev.id

  bigquery_config {
    table = "contrails-301217.${google_bigquery_table.spire-flights-resampled-dev.dataset_id}.${google_bigquery_table.spire-flights-resampled-dev.table_id}"
    use_table_schema = true
    drop_unknown_fields = true
  }

  dead_letter_policy {
    max_delivery_attempts = 5
    dead_letter_topic = google_pubsub_topic.spire_ingest_resample_worker_bigquery_dead_letter_dev.id
  }

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_bigquery_table.spire-flights-resampled-dev,
  ]
}

resource "google_pubsub_subscription" "spire_ingest_resample_worker_bigquery_dead_letter_dev" {
  name  = "spire-ingest-resample-worker-bigquery-dead-letter-dev"
  topic = google_pubsub_topic.spire_ingest_resample_worker_bigquery_dead_letter_dev.id
  message_retention_duration = "86400s"  # 1 day

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.spire_ingest_resample_worker_bigquery_dead_letter_dev,
  ]
}
