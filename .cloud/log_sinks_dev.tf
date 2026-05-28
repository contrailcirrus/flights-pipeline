resource "google_logging_project_sink" "twjf_logs_sink_dev" {
  name        = "trajectory-worker-job-factory-dev-skipped-logs"
  description = "TRAJECTORY-WORKER-JOB-FACTORY: Saves logs about healing, resampling, and validation of trajectory candidates in the development environment."
  destination = "storage.googleapis.com/${google_storage_bucket.twjf_logs_bucket_dev.name}"
  filter      = "resource.type=\"k8s_container\" AND resource.labels.project_id=\"contrails-301217\" AND resource.labels.location=\"us-east1\" AND resource.labels.cluster_name=\"contrails-gke-general\" AND resource.labels.namespace_name=\"flights-pipeline-dev\" AND labels.k8s-pod/app=\"trajectory-worker-job-factory\" AND severity>=INFO"

  exclusions {
    disabled    = false
    filter      = "resource.type=\"k8s_container\" AND resource.labels.project_id=\"contrails-301217\" AND resource.labels.location=\"us-east1\" AND resource.labels.cluster_name=\"contrails-gke-general\" AND resource.labels.namespace_name=\"flights-pipeline-dev\" AND labels.k8s-pod/app=\"trajectory-worker-job-factory\" AND jsonPayload.message=\"zero messages received\""
    name        = "Exclude-zero-messages-received"
  }
  unique_writer_identity = true
}

resource "google_logging_project_sink" "tw_logs_sink_dev" {
  name        = "trajectory-worker-gaia-dev-skipped-logs"
  description = "TRAJECTORY-WORKER: Saves logs for flights handled by the trajectory-worker in the development environment."
  destination = "storage.googleapis.com/${google_storage_bucket.tw_logs_bucket_dev.name}"
  filter      = "resource.type=\"k8s_container\" AND resource.labels.project_id=\"contrails-301217\" AND resource.labels.location=\"us-east1\" AND resource.labels.cluster_name=\"contrails-gke-general\" AND resource.labels.namespace_name=\"flights-pipeline-dev\" AND labels.k8s-pod/app=\"trajectory-worker-gaia\" AND severity>=INFO"

  disabled = false
  unique_writer_identity = true
}

resource "google_logging_project_sink" "tw_backup_logs_sink_dev" {
  name        = "trajectory-worker-gaia-dev-backup-logs"
  description = "TRAJECTORY-WORKER: Saves logs for flights handled by the backup trajectory-worker in the development environment."
  destination = "storage.googleapis.com/${google_storage_bucket.tw_backup_logs_bucket_dev.name}"
  filter      = "resource.type=\"k8s_container\" AND resource.labels.project_id=\"contrails-301217\" AND resource.labels.location=\"us-east1\" AND resource.labels.cluster_name=\"contrails-gke-general\" AND resource.labels.namespace_name=\"flights-pipeline-dev\" AND labels.k8s-pod/app=\"trajectory-worker-gaia-backup\""

  disabled = false
  unique_writer_identity = true
}