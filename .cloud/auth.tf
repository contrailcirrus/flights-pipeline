resource "google_service_account" "flights_pipeline_sa_dev" {
  account_id                   = "flights-pipeline-dev"
  create_ignore_already_exists = null
  description                  = null
  disabled                     = false
  display_name                 = "flights-pipeline-service-account-dev"
  project                      = "contrails-301217"
  timeouts {
    create = null
  }
}

resource "google_project_iam_custom_role" "flights_pipeline_role_dev" {
  description = "Custom role for flights-pipeline services"
  permissions = [
    "datastore.databases.get",
    "datastore.databases.getMetadata",
    "datastore.entities.create",
    "datastore.entities.get",
    "datastore.entities.update",
    "logging.logEntries.create",
    "pubsub.snapshots.seek",
    "pubsub.subscriptions.consume",
    "pubsub.topics.attachSubscription",
    "pubsub.topics.publish",
  ]
  project = "contrails-301217"
  role_id = "flights_pipeline_dev"
  stage   = null
  title   = "flights_pipeline_dev"
}

resource "google_project_iam_member" "flights_pipeline_sa_binding_dev" {
  member  = "serviceAccount:${google_service_account.flights_pipeline_sa.email}"
  project = "contrails-301217"
  role    = google_project_iam_custom_role.flights_pipeline_role.id
  depends_on = [
    google_service_account.flights_pipeline_sa,
    google_project_iam_custom_role.flights_pipeline_role,
  ]
}

resource "google_service_account_iam_binding" "k8s_sa_to_flights_pipeline_sa_binding_dev" {
  service_account_id = google_service_account.flights_pipeline_sa.id
  role               = "roles/iam.workloadIdentityUser"

  members = [
    "serviceAccount:contrails-301217.svc.id.goog[${kubernetes_service_account.flights_pipeline_sa.id}]",
  ]
  depends_on = [
    kubernetes_service_account.flights_pipeline_sa,
    google_service_account.flights_pipeline_sa,
  ]
}
