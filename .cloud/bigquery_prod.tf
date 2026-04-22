resource "google_bigquery_dataset" "flights_pipeline_prod" {
  dataset_id = "flights_pipeline_prod"
  friendly_name = "[PROD] flights pipeline"
  description = "data lake for observation flights data & derived data products"
  location = "US"
  delete_contents_on_destroy = false

  max_time_travel_hours = 168 # 7 days in hours; maximum value
}

resource "google_bigquery_table" "spire_flights_raw_prod" {
  dataset_id = google_bigquery_dataset.flights_pipeline_prod.dataset_id
  table_id   = "spire_flights_raw_prod"
  friendly_name = "[PROD] spire flights, raw"
  description = "raw (first and last waypoint in minute window) flight instances from the Spire API"
  deletion_protection = true
  time_partitioning {
    field = "timestamp"
    type = "DAY"
  }
  clustering = [
    "airline_iata",
    "icao_address",
  ]
  require_partition_filter = true
  schema = file("${path.module}/schemas/bq_spire_flights_raw.json")
  depends_on = [
    google_bigquery_dataset.flights_pipeline_prod,
  ]
}

resource "google_bigquery_table" "trajectory_cocip_prod" {
  dataset_id = google_bigquery_dataset.flights_pipeline_prod.dataset_id
  table_id   = "trajectory_cocip_prod"
  friendly_name = "[PROD] model outputs for trajectory chunks"
  description = "model outputs for a trajectory chunk processed by the trajectory worker"
  deletion_protection = true
  time_partitioning {
    field = "time_start"
    type = "DAY"
  }
  schema = file("${path.module}/schemas/trajectory_worker_chunk.json")
  depends_on = [
    google_bigquery_dataset.flights_pipeline_prod,
  ]
}