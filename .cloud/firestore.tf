resource "google_project_service" "firestore" {
  service = "firestore.googleapis.com"
}

resource "google_firestore_database" "database" {
  name        = "flights-pipeline-dev"
  location_id = "nam5"
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.firestore]
}

# TODO: we should create this doc manually so TF won't make updates to the values
# later. Leaving expected collection/doc_id/doc here for reference until necessary
# environments are setup.
# resource "google_firestore_document" "state" {
#   database    = google_firestore_database.database.id
#   collection  = "state"
#   document_id = "spire-ingest-api-scraper"
#   fields      = jsonencode({ "last_sync_end_at" : timestamp() })
# }
