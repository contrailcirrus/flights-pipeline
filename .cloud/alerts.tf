resource "google_monitoring_alert_policy" "k8scronjob_spire_ingest_api_scraper_prod_checkpoint_behind" {
  display_name = "k8scronjob-spire-ingest-api-scraper-prod-checkpoint-behind"
  combiner     = "OR"

  conditions {
    display_name = "Error in logs"
    condition_matched_log {
      filter = <<EOF
        resource.type="k8s_container"
        resource.labels.cluster_name="contrails-gke-general"
        resource.labels.namespace_name="flights-pipeline-prod"
        labels.k8s-pod/job-name:"spire-ingest-api-scraper-cronjob-"
        jsonPayload.textPayload:"Spire checkpoint behind"
        severity=WARNING
        EOF
    }
  }

  notification_channels = [
    # Nick Masson: SMS
    "projects/contrails-301217/notificationChannels/5296843968149494052",
  ]

  alert_strategy {
    notification_rate_limit {
      period = "3600s"
    }
    auto_close = "86400s"
  }
}
