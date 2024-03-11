resource "google_firestore_database" "database_dev" {
  name        = "flights-pipeline-dev"
  location_id = "nam5"
  type        = "FIRESTORE_NATIVE"
}

resource "google_firestore_database" "database_prod" {
  name        = "flights-pipeline-prod"
  location_id = "nam5"
  type        = "FIRESTORE_NATIVE"
}

# TODO: suggest we build a little Makefile tool for handling first-time instantiation of this document
#       and for any (CAREFUL) updates to it (e.g if we need to slide the pter backwards for backpopulating etc.)
# TODO: we should create this doc manually so TF won't make updates to the values
# later. Leaving expected collection/doc_id/doc here for reference until necessary
# environments are setup.
# resource "google_firestore_document" "state" {
#   database    = google_firestore_database.database.id
#   collection  = "state"
#   document_id = "spire-ingest-api-scraper"
#   fields      = jsonencode({ "last_sync_end_at" : timestamp() })
# }
