resource "google_sql_database_instance" "flight_emissions_report_prod" {
  name             = "flight-emissions-report-prod"
  database_version = "POSTGRES_15"
  region           = "us-east1"

  settings {
    tier = "db-custom-2-7680"

    disk_size = "500"
  }
}

resource "google_sql_database" "flight_emissions_report_prod_flights_pipeline" {
  name     = "flights-pipeline"
  instance = google_sql_database_instance.flight_emissions_report_prod.name

  depends_on = [
    google_sql_database_instance.flight_emissions_report_prod,
  ]
}

resource "google_sql_user" "flight_emissions_report_prod_internal_user_ro" {
  name     = "internal_user_ro"
  instance = google_sql_database_instance.flight_emissions_report_prod.name
  password = "temporarypassword"

  depends_on = [
    google_sql_database.flight_emissions_report_prod_flights_pipeline,
  ]
}

resource "google_sql_user" "flight_emissions_report_prod_internal_user_rw" {
  name     = "internal_user_rw"
  instance = google_sql_database_instance.flight_emissions_report_prod.name
  password = "temporarypassword"

  depends_on = [
    google_sql_database.flight_emissions_report_prod_flights_pipeline,
  ]
}
