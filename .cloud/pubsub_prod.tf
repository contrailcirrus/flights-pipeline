# --------------
# TOPICS
# --------------

resource "google_pubsub_topic" "prod_api_scraper_egress" {
  name = "prod-fp-api-scraper-egress"
}

resource "google_pubsub_topic" "prod_resample_worker_ingress_dead_letter" {
  name = "prod-fp-resample-worker-ingress-dead-letter"
}

resource "google_pubsub_topic" "prod_spire_ingest_raw_bigquery" {
  name = "prod-fp-spire-ingest-raw-bigquery"
}

resource "google_pubsub_topic" "prod_spire_ingest_raw_bigquery_dead_letter" {
  name = "prod-fp-spire-ingest-raw-bigquery-dead-letter"
}

resource "google_pubsub_topic" "prod_spire_ingest_resampled_bigquery" {
  name = "prod-fp-spire-ingest-resampled-bigquery"
}

resource "google_pubsub_topic" "prod_spire_ingest_resampled_bigquery_dead_letter" {
  name = "prod-fp-spire-ingest-resampled-bigquery-dead-letter"
}

resource "google_pubsub_topic" "prod_resample_worker_trajectory_chunk_egress" {
  name = "prod-fp-resample-worker-trajectory-chunk-egress"
}

resource "google_pubsub_topic" "prod_resample_worker_trajectory_chunk_egress_dead_letter" {
  name = "prod-fp-resample-worker-trajectory-chunk-egress-dead-letter"
}

resource "google_pubsub_topic" "prod_gaia_trajectory_chunk" {
  name = "prod-fp-gaia-trajectory-chunk"
}

resource "google_pubsub_topic" "prod_gaia_trajectory_chunk_dead_letter" {
  name = "prod-fp-gaia-trajectory-chunk-dead-letter"
}

resource "google_pubsub_topic" "prod_trajectory_worker_cocip_egress_bigquery" {
  name = "prod-fp-trajectory-worker-cocip-egress-bigquery"
}

resource "google_pubsub_topic" "prod_trajectory_worker_cocip_egress_bigquery_dead_letter" {
  name = "prod-fp-trajectory-worker-cocip-egress-bigquery-dead-letter"
}

# --------------
# SUBSCRIPTIONS
# --------------

resource "google_pubsub_subscription" "prod_spire_ingest_raw_bigquery_delivery" {
  name  = "prod-fp-spire-ingest-raw-bigquery-delivery"
  topic = google_pubsub_topic.prod_spire_ingest_raw_bigquery.id

  bigquery_config {
    table = "contrails-301217.${google_bigquery_table.spire_flights_raw_prod.dataset_id}.${google_bigquery_table.spire_flights_raw_prod.table_id}"
    use_table_schema = true
    drop_unknown_fields = true
  }

  dead_letter_policy {
    max_delivery_attempts = 10
    dead_letter_topic = google_pubsub_topic.prod_spire_ingest_raw_bigquery_dead_letter.id
  }

    retry_policy {
    minimum_backoff = "1s"
    maximum_backoff = "60s"
  }

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_bigquery_table.spire_flights_raw_prod,
    google_pubsub_topic.prod_spire_ingest_raw_bigquery_dead_letter,
  ]
}

resource "google_pubsub_subscription" "prod_spire_ingest_raw_bigquery_dead_letter" {
  name  = "prod-fp-spire-ingest-raw-bigquery-dead-letter"
  topic = google_pubsub_topic.prod_spire_ingest_raw_bigquery_dead_letter.id
  message_retention_duration = "86400s"  # 1 day

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.prod_spire_ingest_raw_bigquery_dead_letter,
  ]
}

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

    dead_letter_policy {
    max_delivery_attempts = 5
    dead_letter_topic = google_pubsub_topic.prod_resample_worker_ingress_dead_letter.id
  }

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.prod_api_scraper_egress,
    google_pubsub_topic.prod_resample_worker_ingress_dead_letter,
  ]
}

resource "google_pubsub_subscription" "prod_resample_worker_ingress_dead_letter" {
  name  = "prod-fp-resample-worker-ingress-dead-letter"
  topic = google_pubsub_topic.prod_resample_worker_ingress_dead_letter.id
  message_retention_duration = "302400s"  # 3.5 day

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.prod_resample_worker_ingress_dead_letter,
  ]
}

resource "google_pubsub_subscription" "prod_spire_ingest_resampled_bigquery_delivery" {
  name  = "prod-fp-spire-ingest-resampled-bigquery-delivery"
  topic = google_pubsub_topic.prod_spire_ingest_resampled_bigquery.id

  bigquery_config {
    table = "contrails-301217.${google_bigquery_table.spire_flights_resampled_prod.dataset_id}.${google_bigquery_table.spire_flights_resampled_prod.table_id}"
    use_table_schema = true
    drop_unknown_fields = true
  }

  dead_letter_policy {
    max_delivery_attempts = 10
    dead_letter_topic = google_pubsub_topic.prod_spire_ingest_resampled_bigquery_dead_letter.id
  }

    retry_policy {
    minimum_backoff = "1s"
    maximum_backoff = "60s"
  }

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_bigquery_table.spire_flights_resampled_prod,
    google_pubsub_topic.prod_spire_ingest_resampled_bigquery_dead_letter
  ]
}

resource "google_pubsub_subscription" "prod_spire_ingest_resampled_bigquery_dead_letter" {
  name  = "prod-fp-spire-ingest-resampled-bigquery-dead-letter"
  topic = google_pubsub_topic.prod_spire_ingest_resampled_bigquery_dead_letter.id
  message_retention_duration = "302400s"  # 3.5 day

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.prod_spire_ingest_resampled_bigquery_dead_letter,
  ]
}

resource "google_pubsub_subscription" "prod_trajectory_worker_realtime_chunk_ingress" {
  name  = "prod-fp-trajectory-worker-realtime-chunk-ingress"
  topic = google_pubsub_topic.prod_resample_worker_trajectory_chunk_egress.id

  ack_deadline_seconds         = 600
  enable_message_ordering      = true
  enable_exactly_once_delivery = true
  message_retention_duration = "302400s"  # 3.5 day

  dead_letter_policy {
    max_delivery_attempts = 5
    dead_letter_topic = google_pubsub_topic.prod_resample_worker_trajectory_chunk_egress_dead_letter.id
  }

  retry_policy {
    minimum_backoff = "30s"
    maximum_backoff = "60s"
  }

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.prod_resample_worker_trajectory_chunk_egress,
    google_pubsub_topic.prod_resample_worker_trajectory_chunk_egress_dead_letter,
  ]
}

resource "google_pubsub_subscription" "prod_trajectory_realtime_chunk_ingress_dead_letter" {
  name  = "prod-fp-trajectory-realtime-chunk-ingress-dead-letter"
  topic = google_pubsub_topic.prod_resample_worker_trajectory_chunk_egress_dead_letter.id
  message_retention_duration = "302400s"  # 3.5 day

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.prod_resample_worker_trajectory_chunk_egress_dead_letter,
  ]
}

resource "google_pubsub_subscription" "prod_trajectory_worker_gaia_chunk_ingress" {
  name  = "prod-fp-trajectory-worker-gaia-chunk-ingress"
  topic = google_pubsub_topic.prod_gaia_trajectory_chunk.id

  ack_deadline_seconds         = 600
  enable_message_ordering      = true
  enable_exactly_once_delivery = true
  message_retention_duration = "302400s"  # 3.5 day

  dead_letter_policy {
    max_delivery_attempts = 5
    dead_letter_topic = google_pubsub_topic.prod_gaia_trajectory_chunk_dead_letter.id
  }

  retry_policy {
    minimum_backoff = "30s"
    maximum_backoff = "60s"
  }

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.prod_gaia_trajectory_chunk,
    google_pubsub_topic.prod_gaia_trajectory_chunk_dead_letter,
  ]
}

resource "google_pubsub_subscription" "prod_trajectory_gaia_chunk_ingress_dead_letter" {
  name  = "prod-fp-trajectory-gaia-chunk-ingress-dead-letter"
  topic = google_pubsub_topic.prod_gaia_trajectory_chunk_dead_letter.id
  message_retention_duration = "604800s"  # 7 day

  expiration_policy {
    ttl = ""
  }
  ack_deadline_seconds = 60

  depends_on = [
    google_pubsub_topic.prod_gaia_trajectory_chunk_dead_letter,
  ]
}

resource "google_pubsub_subscription" "prod_trajectory_worker_cocip_bigquery_delivery" {
  name  = "prod-fp-trajectory-worker-cocip-bigquery-delivery"
  topic = google_pubsub_topic.prod_trajectory_worker_cocip_egress_bigquery.id

  bigquery_config {
    table = "contrails-301217.${google_bigquery_table.trajectory_cocip_prod.dataset_id}.${google_bigquery_table.trajectory_cocip_prod.table_id}"
    use_table_schema = true
    drop_unknown_fields = true
  }

  dead_letter_policy {
    max_delivery_attempts = 15
    dead_letter_topic = google_pubsub_topic.prod_trajectory_worker_cocip_egress_bigquery_dead_letter.id
  }

  ack_deadline_seconds = 30

    retry_policy {
    minimum_backoff = "1s"
    maximum_backoff = "60s"
  }

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_bigquery_table.trajectory_cocip_prod,
    google_pubsub_topic.prod_trajectory_worker_cocip_egress_bigquery_dead_letter,
  ]
}

resource "google_pubsub_subscription" "prod_trajectory_worker_cocip_bigquery_dead_letter" {
  name  = "prod-fp-trajectory-worker-cocip-bigquery-dead-letter"
  topic = google_pubsub_topic.prod_trajectory_worker_cocip_egress_bigquery_dead_letter.id
  message_retention_duration = "302400s"  # 3.5 day

  expiration_policy {
    ttl = ""
  }

  depends_on = [
    google_pubsub_topic.prod_trajectory_worker_cocip_egress_bigquery_dead_letter,
  ]
}