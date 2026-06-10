# Set up development buckets to hold logs

resource "google_storage_bucket" "twjf_logs_bucket_dev" {
  name          = "contrails-301217-fp-dev-trajectory-worker-job-factory"
  project       = data.google_project.project.project_id
  location      = "us"
  enable_object_retention = false
  requester_pays = false
  hierarchical_namespace {
    enabled = false
  }
  soft_delete_policy {
    retention_duration_seconds = 604800
  }
}

resource "google_storage_bucket" "tw_logs_bucket_dev" {
  name          = "contrails-301217-fp-dev-trajectory-worker"
  project       = data.google_project.project.project_id
  location      = "us"
  enable_object_retention = false
  requester_pays = false
  hierarchical_namespace {
    enabled = false
  }
  soft_delete_policy {
      retention_duration_seconds = 604800
  }
}


resource "google_storage_bucket" "tw_backup_logs_bucket_dev" {
  name          = "contrails-301217-fp-dev-trajectory-worker-backup"
  project       = data.google_project.project.project_id
  location      = "us-east1"
  enable_object_retention = false
  requester_pays = false
  hierarchical_namespace {
    enabled = true
  }
  soft_delete_policy {
    retention_duration_seconds = 604800
  }
}


# Set up production buckets to hold logs

resource "google_storage_bucket" "twjf_logs_bucket_prod" {
  name          = "contrails-301217-fp-prod-trajectory-worker-job-factory"
  project       = data.google_project.project.project_id
  location      = "us"
  enable_object_retention = false
  requester_pays = false
  hierarchical_namespace {
    enabled = false
  }
  soft_delete_policy {
    retention_duration_seconds = 604800
  }
}

resource "google_storage_bucket" "tw_logs_bucket_prod" {
  name          = "contrails-301217-fp-prod-trajectory-worker"
  project       = data.google_project.project.project_id
  location      = "us"
  enable_object_retention = false
  requester_pays = false
  hierarchical_namespace {
    enabled = false
  }
  soft_delete_policy {
      retention_duration_seconds = 604800
  }
}


resource "google_storage_bucket" "tw_backup_logs_bucket_prod" {
  name          = "contrails-301217-fp-prod-trajectory-worker-backup"
  project       = data.google_project.project.project_id
  location      = "us-east1"
  enable_object_retention = false
  requester_pays = false
  hierarchical_namespace {
    enabled = true
  }
  soft_delete_policy {
    retention_duration_seconds = 604800
  }
}