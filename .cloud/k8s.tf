resource "kubernetes_namespace" "flights_pipeline_dev" {
  metadata {
    annotations = {
      name = "flights-pipeline-dev"
    }
    labels = {
      name = "flights-pipeline-dev"
    }
    name = "flights-pipeline-dev"
  }
}

resource "kubernetes_namespace" "flights_pipeline_prod" {
  metadata {
    annotations = {
      name = "flights-pipeline-prod"
    }
    labels = {
      name = "flights-pipeline-prod"
    }
    name = "flights-pipeline-prod"
  }
}

resource "kubernetes_service_account" "flights_pipeline_sa_dev" {
  metadata {
    name      = "flights-pipeline-default-sa"
    namespace = kubernetes_namespace.flights_pipeline_dev.id
    annotations = {
      "iam.gke.io/gcp-service-account" = google_service_account.flights_pipeline_sa.email
    }
  }
  depends_on = [
    google_service_account.flights_pipeline_sa,
    kubernetes_namespace.flights_pipeline_dev,
  ]
}

resource "kubernetes_service_account" "flights_pipeline_sa_prod" {
  metadata {
    name      = "flights-pipeline-default-sa"
    namespace = kubernetes_namespace.flights_pipeline_prod.id
    annotations = {
      "iam.gke.io/gcp-service-account" = google_service_account.flights_pipeline_sa.email
    }
  }
  depends_on = [
    google_service_account.flights_pipeline_sa,
    kubernetes_namespace.flights_pipeline_prod,
  ]
}