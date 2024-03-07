resource "kubernetes_namespace" "flights_pipeline" {
  metadata {
    annotations = {
      name = "flights-pipeline-${var.env}"
    }
    labels = {
      name = "flights-pipeline-${var.env}"
    }
    name = "flights-pipeline-${var.env}"
  }
}

resource "kubernetes_service_account" "flights_pipeline_sa" {
  metadata {
    name      = "flights-pipeline-default-sa-${var.env}"
    namespace = kubernetes_namespace.flights_pipeline.id
    annotations = {
      "iam.gke.io/gcp-service-account" = google_service_account.flights_pipeline_sa.email
    }
  }
  depends_on = [
    google_service_account.flights_pipeline_sa,
  ]
}
