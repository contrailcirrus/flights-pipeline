# --------------
# TOPICS
# --------------

resource "google_pubsub_topic" "dev_api_scraper_egress" {
  name = "dev-fp-api-scraper-egress"
}

resource "google_pubsub_topic" "dev_resample_worker_ingress_dead_letter" {
  name = "dev-fp-resample-worker-ingress-dead-letter"
}

resource "google_pubsub_topic" "dev_spire_ingest_raw_bigquery" {
  name = "dev-fp-spire-ingest-raw-bigquery"
}

resource "google_pubsub_topic" "dev_spire_ingest_raw_bigquery_dead_letter" {
  name = "dev-fp-spire-ingest-raw-bigquery-dead-letter"
}

resource "google_pubsub_topic" "dev_spire_ingest_resampled_bigquery" {
  name = "dev-fp-spire-ingest-resampled-bigquery"
}

resource "google_pubsub_topic" "dev_spire_ingest_resampled_bigquery_dead_letter" {
  name = "dev-fp-spire-ingest-resampled-bigquery-dead-letter"
}

resource "google_pubsub_topic" "dev_resample_worker_trajectory_chunk_egress" {
  name = "dev-fp-resample-worker-trajectory-chunk-egress"
}

resource "google_pubsub_topic" "dev_resample_worker_trajectory_chunk_egress_dead_letter" {
  name = "dev-fp-resample-worker-trajectory-chunk-egress-dead-letter"
}

resource "google_pubsub_topic" "dev_gaia_trajectory_chunk" {
  name = "dev-fp-gaia-trajectory-chunk"
}

resource "google_pubsub_topic" "dev_gaia_trajectory_chunk_dead_letter" {
  name = "dev-fp-gaia-trajectory-chunk-dead-letter"
}

resource "google_pubsub_topic" "dev_trajectory_worker_cocip_egress_bigquery" {
  name = "dev-fp-trajectory-worker-cocip-egress-bigquery"
}

resource "google_pubsub_topic" "dev_trajectory_worker_cocip_egress_bigquery_dead_letter" {
  name = "dev-fp-trajectory-worker-cocip-egress-bigquery-dead-letter"
}

# --------------
# SUBSCRIPTIONS
# --------------

resource "google_pubsub_subscription" "dev_spire_ingest_raw_bigquery_delivery" {
  name  = "dev-fp-spire-ingest-raw-bigquery-delivery"
  topic = google_pubsub_topic.dev_spire_ingest_raw_bigquery.id

  bigquery_config {
    table = "contrails-301217.${google_bigquery_table.spire_flights_raw_dev.dataset_id}.${google_bigquery_table.spire_flights_raw_dev.table_id}"
    use_table_schema = true
    drop_unknown_fields = true
  }

  dead_letter_policy {
    max_delivery_attempts = 10
    dead_letter_topic = google_pubsub_topic.dev_spire_ingest_raw_bigquery_dead_letter.id
  }

    retry_policy {
    minimum_backoff = "1s"
    maximum_backoff = "60s"
  }

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_bigquery_table.spire_flights_raw_dev,
    google_pubsub_topic.dev_spire_ingest_raw_bigquery_dead_letter,
  ]
}

resource "google_pubsub_subscription" "dev_spire_ingest_raw_bigquery_dead_letter" {
  name  = "dev-fp-spire-ingest-raw-bigquery-dead-letter"
  topic = google_pubsub_topic.dev_spire_ingest_raw_bigquery_dead_letter.id
  message_retention_duration = "86400s"  # 1 day

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.dev_spire_ingest_raw_bigquery_dead_letter,
  ]
}

resource "google_pubsub_subscription" "dev_resample_worker_ingress" {
  name  = "dev-fp-resample-worker-ingress"
  topic = google_pubsub_topic.dev_api_scraper_egress.id

  ack_deadline_seconds         = 300
  enable_message_ordering      = true
  enable_exactly_once_delivery = true
  message_retention_duration = "86400s"  # 1 day

  retry_policy {
    minimum_backoff = "1s"
    maximum_backoff = "4s"
  }

  dead_letter_policy {
    max_delivery_attempts = 5
    dead_letter_topic = google_pubsub_topic.dev_resample_worker_ingress_dead_letter.id
  }

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.dev_api_scraper_egress,
    google_pubsub_topic.dev_resample_worker_ingress_dead_letter,
  ]
}

resource "google_pubsub_subscription" "dev_resample_worker_ingress_dead_letter" {
  name  = "dev-fp-resample-worker-ingress-dead-letter"
  topic = google_pubsub_topic.dev_resample_worker_ingress_dead_letter.id
  message_retention_duration = "86400s"  # 1 day

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.dev_resample_worker_ingress_dead_letter,
  ]
}

resource "google_pubsub_subscription" "dev_spire_ingest_resampled_bigquery_delivery" {
  name  = "dev-fp-spire-ingest-resampled-bigquery-delivery"
  topic = google_pubsub_topic.dev_spire_ingest_resampled_bigquery.id

  bigquery_config {
    table = "contrails-301217.${google_bigquery_table.spire_flights_resampled_dev.dataset_id}.${google_bigquery_table.spire_flights_resampled_dev.table_id}"
    use_table_schema = true
    drop_unknown_fields = true
  }

  dead_letter_policy {
    max_delivery_attempts = 10
    dead_letter_topic = google_pubsub_topic.dev_spire_ingest_resampled_bigquery_dead_letter.id
  }

    retry_policy {
    minimum_backoff = "1s"
    maximum_backoff = "60s"
  }

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_bigquery_table.spire_flights_resampled_dev,
    google_pubsub_topic.dev_spire_ingest_resampled_bigquery_dead_letter
  ]
}

resource "google_pubsub_subscription" "dev_spire_ingest_resampled_bigquery_dead_letter" {
  name  = "dev-fp-spire-ingest-resampled-bigquery-dead-letter"
  topic = google_pubsub_topic.dev_spire_ingest_resampled_bigquery_dead_letter.id
  message_retention_duration = "86400s"  # 1 day

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.dev_spire_ingest_resampled_bigquery_dead_letter,
  ]
}

resource "google_pubsub_subscription" "dev_trajectory_worker_realtime_chunk_ingress" {
  name  = "dev-fp-trajectory-worker-realtime-chunk-ingress"
  topic = google_pubsub_topic.prod_resample_worker_trajectory_chunk_egress.id

  ack_deadline_seconds         = 600
  enable_message_ordering      = true
  enable_exactly_once_delivery = true
  message_retention_duration = "86400s"  # 1 day

  dead_letter_policy {
    max_delivery_attempts = 5
    dead_letter_topic = google_pubsub_topic.dev_resample_worker_trajectory_chunk_egress_dead_letter.id
  }

  retry_policy {
    minimum_backoff = "30s"
    maximum_backoff = "60s"
  }

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.dev_resample_worker_trajectory_chunk_egress,
    google_pubsub_topic.dev_resample_worker_trajectory_chunk_egress_dead_letter,
  ]
}

resource "google_pubsub_subscription" "dev_trajectory_realtime_chunk_ingress_dead_letter" {
  name  = "dev-fp-trajectory-realtime-chunk-ingress-dead-letter"
  topic = google_pubsub_topic.dev_resample_worker_trajectory_chunk_egress_dead_letter.id
  message_retention_duration = "86400s"  # 1 day

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.dev_resample_worker_trajectory_chunk_egress_dead_letter,
  ]
}

resource "google_pubsub_subscription" "dev_trajectory_worker_gaia_chunk_ingress" {
  name  = "dev-fp-trajectory-worker-gaia-chunk-ingress"
  topic = google_pubsub_topic.dev_gaia_trajectory_chunk.id

  ack_deadline_seconds         = 600
  enable_message_ordering      = true
  enable_exactly_once_delivery = true
  message_retention_duration = "86400s"  # 1 day

  dead_letter_policy {
    max_delivery_attempts = 5
    dead_letter_topic = google_pubsub_topic.dev_gaia_trajectory_chunk_dead_letter.id
  }

  retry_policy {
    minimum_backoff = "30s"
    maximum_backoff = "60s"
  }

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.dev_gaia_trajectory_chunk,
    google_pubsub_topic.dev_gaia_trajectory_chunk_dead_letter,
  ]
}

resource "google_pubsub_subscription" "dev_trajectory_gaia_chunk_ingress_dead_letter" {
  name  = "dev-fp-trajectory-gaia-chunk-ingress-dead-letter"
  topic = google_pubsub_topic.dev_gaia_trajectory_chunk_dead_letter.id
  message_retention_duration = "86400s"  # 1 day

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.dev_gaia_trajectory_chunk_dead_letter,
  ]
}

resource "google_pubsub_subscription" "dev_trajectory_worker_cocip_bigquery_delivery" {
  name  = "dev-fp-trajectory-worker-cocip-bigquery-delivery"
  topic = google_pubsub_topic.dev_trajectory_worker_cocip_egress_bigquery.id

  bigquery_config {
    table = "contrails-301217.${google_bigquery_table.trajectory_cocip_dev.dataset_id}.${google_bigquery_table.trajectory_cocip_dev.table_id}"
    use_table_schema = true
    drop_unknown_fields = true
  }

  dead_letter_policy {
    max_delivery_attempts = 10
    dead_letter_topic = google_pubsub_topic.dev_trajectory_worker_cocip_egress_bigquery_dead_letter.id
  }

    retry_policy {
    minimum_backoff = "1s"
    maximum_backoff = "60s"
  }

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_bigquery_table.trajectory_cocip_dev,
    google_pubsub_topic.dev_trajectory_worker_cocip_egress_bigquery_dead_letter,
  ]
}

resource "google_pubsub_subscription" "dev_trajectory_worker_cocip_bigquery_dead_letter_dev" {
  name  = "dev-fp-trajectory-worker-cocip-bigquery-dead-letter-dev"
  topic = google_pubsub_topic.dev_trajectory_worker_cocip_egress_bigquery_dead_letter.id
  message_retention_duration = "86400s"  # 1 day

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.dev_trajectory_worker_cocip_egress_bigquery_dead_letter,
  ]
}
