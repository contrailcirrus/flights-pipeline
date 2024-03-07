resource "google_artifact_registry_repository" "flights_pipeline_dev" {
  location      = "us-east1"
  repository_id = "flights-pipeline-dev"
  description   = "flights-pipeline docker images"
  format        = "DOCKER"
}
