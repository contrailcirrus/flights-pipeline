resource "google_artifact_registry_repository" "flights_pipeline" {
  location      = "us-east1"
  repository_id = "flights-pipeline-${var.env}"
  description   = "flights-pipeline docker images"
  format        = "DOCKER"
}
