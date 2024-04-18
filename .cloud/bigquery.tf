resource "google_bigquery_dataset" "flights-pipeline-dev" {
  dataset_id = "flights_pipeline_dev"
  friendly_name = "[DEV] flights pipeline"
  description = "data lake for observation flights data & derived data products"
  location = "US"
  delete_contents_on_destroy = false
}

resource "google_bigquery_dataset" "flights-pipeline-prod" {
  dataset_id = "flights_pipeline_prod"
  friendly_name = "[PROD] flights pipeline"
  description = "data lake for observation flights data & derived data products"
  location = "US"
  delete_contents_on_destroy = false
}

resource "google_bigquery_table" "spire-flights-resampled-dev" {
  dataset_id = google_bigquery_dataset.flights-pipeline-dev.dataset_id
  table_id   = "spire_flights_resampled_dev"
  friendly_name = "[DEV] spire flights, resampled"
  description = "resampled and interpolated flight instances from the Spire API"
  deletion_protection = true
  time_partitioning {
    field = "timestamp"
    type = "DAY"
  }
  schema = file("${path.module}/schemas/bq_spire_flights_resampled.json")
  depends_on = [
    google_bigquery_dataset.flights-pipeline-dev,
  ]
}

resource "google_bigquery_table" "spire-flights-raw-dev" {
  dataset_id = google_bigquery_dataset.flights-pipeline-dev.dataset_id
  table_id   = "spire_flights_raw_dev"
  friendly_name = "[DEV] spire flights, raw"
  description = "raw (first and last waypoint in minute window) flight instances from the Spire API"
  deletion_protection = true
  time_partitioning {
    field = "timestamp"
    type = "DAY"
  }
  schema = file("${path.module}/schemas/bq_spire_flights_raw.json")
  depends_on = [
    google_bigquery_dataset.flights-pipeline-dev,
  ]
}

resource "google_bigquery_table" "trajectory-cocip-dev" {
  dataset_id = google_bigquery_dataset.flights-pipeline-dev.dataset_id
  table_id   = "trajectory_cocip_dev"
  friendly_name = "[DEV] model outputs for trajectory chunks"
  description = "model outputs for a trajectory chunk processed by the trajectory worker"
  deletion_protection = true
  time_partitioning {
    field = "timestamp"
    type = "DAY"
  }
  schema = file("${path.module}/schemas/trajectory_worker_chunk.json")
  depends_on = [
    google_bigquery_dataset.flights-pipeline-dev,
  ]
}
