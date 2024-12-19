# flight emissions report cache database
resource "google_sql_database" "flights_pipeline_fer_cache_prod" {
  name     = "flights-pipeline-fer-cache"
  instance = "contrails-default-prod"
}

