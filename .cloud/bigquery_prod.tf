resource "google_bigquery_dataset" "flights_pipeline_prod" {
  dataset_id = "flights_pipeline_prod"
  friendly_name = "[PROD] flights pipeline"
  description = "data lake for observation flights data & derived data products"
  location = "US"
  delete_contents_on_destroy = false
}
