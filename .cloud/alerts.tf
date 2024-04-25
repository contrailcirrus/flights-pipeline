resource "google_monitoring_alert_policy" "k8scronjob_spire_ingest_api_scraper_prod_error_in_logs" {
  display_name = "k8scronjob-spire-ingest-api-scraper-prod-error-in-logs"
  combiner     = "OR"

  conditions {
    display_name = "Error in logs"
    condition_matched_log {
      filter = <<EOF
        resource.type="k8s_container"
        resource.labels.cluster_name="contrails-gke-general"
        resource.labels.namespace_name="flights-pipeline-prod"
        labels.k8s-pod/job-name:"spire-ingest-api-scraper-cronjob-"
        severity>=ERROR
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

resource "google_monitoring_alert_policy" "k8sdeployment_spire_ingest_resample_worker_prod_error_in_logs" {
  display_name = "k8sdeployment-spire-ingest-resample-worker-prod-error-in-logs"
  combiner     = "OR"

  conditions {
    display_name = "Error in logs"
    condition_matched_log {
      filter = <<EOF
        resource.type="k8s_container"
        resource.labels.cluster_name="contrails-gke-general"
        resource.labels.namespace_name="flights-pipeline-prod"
        labels.k8s-pod/app="spire-ingest-resample-worker"
        severity>=ERROR
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

resource "google_monitoring_alert_policy" "k8sdeployment_trajectory_worker_realtime_prod_error_in_logs" {
  display_name = "k8sdeployment-trajectory-worker-realtime-prod-error-in-logs"
  combiner     = "OR"

  conditions {
    display_name = "Error in logs"
    condition_matched_log {
      filter = <<EOF
        resource.type="k8s_container"
        resource.labels.cluster_name="contrails-gke-general"
        resource.labels.namespace_name="flights-pipeline-prod"
        labels.k8s-pod/app="trajectory-worker-realtime"
        severity>=ERROR
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

resource "google_monitoring_alert_policy" "k8sdeployment_trajectory_worker_batch_prod_error_in_logs" {
  display_name = "k8sdeployment-trajectory-worker-batch-prod-error-in-logs"
  combiner     = "OR"

  conditions {
    display_name = "Error in logs"
    condition_matched_log {
      filter = <<EOF
        resource.type="k8s_container"
        resource.labels.cluster_name="contrails-gke-general"
        resource.labels.namespace_name="flights-pipeline-prod"
        labels.k8s-pod/app="trajectory-worker-batch"
        severity>=ERROR
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
