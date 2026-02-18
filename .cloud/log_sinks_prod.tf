# Set up buckets to hold logs

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


resource "google_logging_project_sink" "twjf_logs_sink_prod" {
  name        = "trajectory-worker-job-factory-prod-skipped-logs"
  description = "TRAJECTORY-WORKER-JOB-FACTORY: Saves logs about healing, resampling, and validation of trajectory candidates in the production environment."
  destination = "storage.googleapis.com/${google_storage_bucket.twjf_logs_bucket_prod.name}"
  filter      = "resource.type=\"k8s_container\" AND resource.labels.project_id=\"contrails-301217\" AND resource.labels.location=\"us-east1\" AND resource.labels.cluster_name=\"contrails-gke-general\" AND resource.labels.namespace_name=\"flights-pipeline-prod\" AND labels.k8s-pod/app=\"trajectory-worker-job-factory\" AND severity>=INFO"

  unique_writer_identity = true
}

resource "google_logging_project_sink" "tw_logs_sink_prod" {
  name        = "trajectory-worker-gaia-prod-skipped-logs"
  description = "TRAJECTORY-WORKER: Saves logs for flights handled by the trajectory-worker in the production environment."
  destination = "storage.googleapis.com/${google_storage_bucket.tw_logs_bucket_prod.name}"
  filter      = "resource.type=\"k8s_container\" AND resource.labels.project_id=\"contrails-301217\" AND resource.labels.location=\"us-east1\" AND resource.labels.cluster_name=\"contrails-gke-general\" AND resource.labels.namespace_name=\"flights-pipeline-prod\" AND labels.k8s-pod/app=\"trajectory-worker-gaia\" AND severity>=INFO"

  disabled = false
  unique_writer_identity = true
}

resource "google_logging_project_sink" "tw_backup_logs_sink_prod" {
  name        = "trajectory-worker-gaia-prod-backup-logs"
  description = "TRAJECTORY-WORKER: Saves logs for flights handled by the backup trajectory-worker in the production environment."
  destination = "storage.googleapis.com/${google_storage_bucket.tw_backup_logs_bucket_prod.name}"
  filter      = "resource.type=\"k8s_container\" AND resource.labels.project_id=\"contrails-301217\" AND resource.labels.location=\"us-east1\" AND resource.labels.cluster_name=\"contrails-gke-general\" AND resource.labels.namespace_name=\"flights-pipeline-prod\" AND labels.k8s-pod/app=\"trajectory-worker-gaia-backup\""

  disabled = false
  unique_writer_identity = true
}