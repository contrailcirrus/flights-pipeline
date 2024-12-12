# flight emissions report cache database
resource "google_sql_database" "flights_pipeline_fer_cache_dev" {
  name     = "flights-pipeline-fer-cache"
  instance = "contrails-default-dev"
}
