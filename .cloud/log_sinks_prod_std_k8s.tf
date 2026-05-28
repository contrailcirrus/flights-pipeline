resource "google_logging_project_sink" "twjf_logs_sink_prod_std" {
  name        = "trajectory-worker-job-factory-prod-std-skipped-logs"
  description = "TRAJECTORY-WORKER-JOB-FACTORY: Saves logs about healing, resampling, and validation of trajectory candidates in the production environment."
  destination = "storage.googleapis.com/${google_storage_bucket.twjf_logs_bucket_prod.name}"
  filter      = "resource.type=\"k8s_container\" AND resource.labels.project_id=\"contrails-301217\" AND resource.labels.location=\"us-east4\" AND resource.labels.cluster_name=\"contrails-gke-general-std-useast4\" AND resource.labels.namespace_name=\"flights-pipeline-prod\" AND labels.k8s-pod/app=\"trajectory-worker-job-factory\" AND severity>=INFO"

  exclusions {
    disabled    = false
    filter      = "resource.type=\"k8s_container\" AND resource.labels.project_id=\"contrails-301217\" AND resource.labels.location=\"us-east4\" AND resource.labels.cluster_name=\"contrails-gke-general-std-useast4\" AND resource.labels.namespace_name=\"flights-pipeline-prod\" AND labels.k8s-pod/app=\"trajectory-worker-job-factory\" AND jsonPayload.message=\"zero messages received\""
    name        = "Exclude-zero-messages-received"
  }
  unique_writer_identity = true
}

resource "google_logging_project_sink" "tw_logs_sink_prod_std" {
  name        = "trajectory-worker-gaia-prod-std-skipped-logs"
  description = "TRAJECTORY-WORKER: Saves logs for flights handled by the trajectory-worker in the production environment."
  destination = "storage.googleapis.com/${google_storage_bucket.tw_logs_bucket_prod.name}"
  filter      = "resource.type=\"k8s_container\" AND resource.labels.project_id=\"contrails-301217\" AND resource.labels.location=\"us-east4\" AND resource.labels.cluster_name=\"contrails-gke-general-std-useast4\" AND resource.labels.namespace_name=\"flights-pipeline-prod\" AND labels.k8s-pod/app=\"trajectory-worker-gaia\" AND severity>=INFO"

  disabled = false
  unique_writer_identity = true
}

resource "google_logging_project_sink" "tw_backup_logs_sink_prod_std" {
  name        = "trajectory-worker-gaia-prod-std-backup-logs"
  description = "TRAJECTORY-WORKER: Saves logs for flights handled by the backup trajectory-worker in the production environment."
  destination = "storage.googleapis.com/${google_storage_bucket.tw_backup_logs_bucket_prod.name}"
  filter      = "resource.type=\"k8s_container\" AND resource.labels.project_id=\"contrails-301217\" AND resource.labels.location=\"us-east4\" AND resource.labels.cluster_name=\"contrails-gke-general-std-useast4\" AND resource.labels.namespace_name=\"flights-pipeline-prod\" AND labels.k8s-pod/app=\"trajectory-worker-gaia-backup\""

  disabled = false
  unique_writer_identity = true
}