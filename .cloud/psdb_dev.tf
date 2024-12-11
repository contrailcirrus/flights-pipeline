# flight emissions report cache database
resource "google_sql_database" "flights_pipeline_fer_cache_dev" {
  name     = "flights-pipeline-fer-cache"
  instance = "contrails-default-dev"
}

# ----
# TODO
# remove psdb instances; remove secrets from k8s

resource "google_sql_database_instance" "flight_emissions_report_dev" {
  name             = "flight-emissions-report-dev"
  database_version = "POSTGRES_15"
  region           = "us-east1"

  settings {
    tier = "db-custom-1-3840"

    disk_size = "100"
  }
}

resource "google_sql_database" "flight_emissions_report_dev_flights_pipeline" {
  name     = "flights-pipeline"
  instance = google_sql_database_instance.flight_emissions_report_dev.name

  depends_on = [
    google_sql_database_instance.flight_emissions_report_dev,
  ]
}

resource "google_sql_user" "flight_emissions_report_dev_internal_user_ro" {
  name     = "internal_user_ro"
  instance = google_sql_database_instance.flight_emissions_report_dev.name
  password = "temporarypassword"

  depends_on = [
    google_sql_database.flight_emissions_report_dev_flights_pipeline,
  ]
}

resource "google_sql_user" "flight_emissions_report_dev_internal_user_rw" {
  name     = "internal_user_rw"
  instance = google_sql_database_instance.flight_emissions_report_dev.name
  password = "temporarypassword"

  depends_on = [
    google_sql_database.flight_emissions_report_dev_flights_pipeline,
  ]
}
