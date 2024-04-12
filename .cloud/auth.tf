resource "google_service_account" "flights_pipeline_sa" {
  account_id                   = "flights-pipeline"
  create_ignore_already_exists = null
  description                  = null
  disabled                     = false
  display_name                 = "flights-pipeline-service-account"
  project                      = "contrails-301217"
  timeouts {
    create = null
  }
}

resource "google_project_iam_custom_role" "flights_pipeline_role" {
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
    "storage.objects.list",
    "storage.objects.get",
  ]
  project = "contrails-301217"
  role_id = "flights_pipeline"
  stage   = null
  title   = "flights_pipeline"
}

resource "google_project_iam_member" "flights_pipeline_sa_binding" {
  member  = "serviceAccount:${google_service_account.flights_pipeline_sa.email}"
  project = "contrails-301217"
  role    = google_project_iam_custom_role.flights_pipeline_role.id
  depends_on = [
    google_service_account.flights_pipeline_sa,
    google_project_iam_custom_role.flights_pipeline_role,
  ]
}


resource "google_service_account_iam_binding" "k8s_sa_to_flights_pipeline_sa_binding" {
  service_account_id = google_service_account.flights_pipeline_sa.id
  role               = "roles/iam.workloadIdentityUser"

  members = [
    "serviceAccount:contrails-301217.svc.id.goog[${kubernetes_service_account.flights_pipeline_sa_dev.id}]",
    "serviceAccount:contrails-301217.svc.id.goog[${kubernetes_service_account.flights_pipeline_sa_prod.id}]",
  ]
  depends_on = [
    kubernetes_service_account.flights_pipeline_sa_dev,
    kubernetes_service_account.flights_pipeline_sa_prod,
    google_service_account.flights_pipeline_sa,
  ]
}

# this is a pre-existing, google-managed service account tied to pubsub
# ----------------
# these roles are required for the pubsub -> bigquery integration
resource "google_project_iam_member" "pubsub_to_bigquery_sa_binding_viever" {
  project = "contrails-301217"
  role   = "roles/bigquery.metadataViewer"
  member = "serviceAccount:service-577335432373@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "pubsub_to_bigquery_sa_binding_editor" {
  project = "contrails-301217"
  role   = "roles/bigquery.dataEditor"
  member = "serviceAccount:service-577335432373@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# these roles are required for subscribers to publish failed msgs to a dead letter topic
resource "google_project_iam_member" "pubsub_to_dead_letter_sa_binding_publisher" {
  project = "contrails-301217"
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:service-577335432373@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "pubsub_to_dead_letter_sa_binding_subscriber" {
  project = "contrails-301217"
  role   = "roles/pubsub.subscriber"
  member = "serviceAccount:service-577335432373@gcp-sa-pubsub.iam.gserviceaccount.com"
}
