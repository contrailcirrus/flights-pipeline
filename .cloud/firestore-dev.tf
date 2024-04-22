resource "google_firestore_database" "database_dev" {
  name        = "flights-pipeline-dev"
  location_id = "nam5"
  type        = "FIRESTORE_NATIVE"
}
