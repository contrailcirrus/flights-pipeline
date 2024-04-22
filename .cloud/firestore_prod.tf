resource "google_firestore_database" "database_prod" {
  name        = "flights-pipeline-prod"
  location_id = "nam5"
  type        = "FIRESTORE_NATIVE"
}
