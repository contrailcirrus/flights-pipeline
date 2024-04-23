resource "google_redis_instance" "flights_pipeline_redis_cache_dev" {
  name           = "flights-pipeline-dev"
  tier           = "STANDARD_HA"
  memory_size_gb = 1

  location_id             = "us-east1-c"
  alternative_location_id = "us-east1-b"

  redis_version     = "REDIS_7_0"
  display_name      = "flight-instance-dev"

  read_replicas_mode = "READ_REPLICAS_DISABLED"
  replica_count = 1

  maintenance_policy {
    weekly_maintenance_window {
      day = "TUESDAY"
      start_time {
        hours = 0
        minutes = 30
        seconds = 0
        nanos = 0
      }
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}
