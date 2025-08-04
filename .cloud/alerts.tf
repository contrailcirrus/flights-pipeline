# 
# api-scraper
# 

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

    # Mahesh Saripalli: SMS 
    "projects/contrails-301217/notificationChannels/12238957771652159581",
  ]

  alert_strategy {
    notification_rate_limit {
      period = "3600s"
    }
    auto_close = "86400s"
  }
}

resource "google_monitoring_alert_policy" "pubsubtopic_prod_api_scraper_bigquery_egress_publish_count" {
  display_name = "pubsubtopic-${google_pubsub_topic.prod_spire_ingest_raw_bigquery.name}-publish-count"
  combiner     = "OR"

  conditions {
    display_name = "Publish count below threshold"
    condition_monitoring_query_language {
      query    = <<EOF
        fetch pubsub_topic
        | metric 'pubsub.googleapis.com/topic/message_sizes'
        | filter resource.topic_id == '${google_pubsub_topic.prod_spire_ingest_raw_bigquery.name}'
        | group_by sliding(30m), row_count()
        | every 1m
        | condition val() < 10
        EOF
      duration = "0s"
    }
  }

  notification_channels = [
    # Nick Masson: SMS
    "projects/contrails-301217/notificationChannels/5296843968149494052",
     # Mahesh Saripalli: SMS 
    "projects/contrails-301217/notificationChannels/12238957771652159581",
  ]
}

resource "google_monitoring_alert_policy" "pubsubtopic_prod_api_scraper_bigquery_egress_dead_letter_publish_count" {
  display_name = "pubsubtopic-${google_pubsub_topic.prod_spire_ingest_raw_bigquery_dead_letter.name}-publish-count"
  combiner     = "OR"

  conditions {
    display_name = "Publish count above threshold"
    condition_monitoring_query_language {
      query    = <<EOF
        fetch pubsub_topic
        | metric 'pubsub.googleapis.com/topic/message_sizes'
        | filter resource.topic_id == '${google_pubsub_topic.prod_spire_ingest_raw_bigquery_dead_letter.name}'
        | group_by sliding(30m), row_count()
        | every 1m
        | condition val() > 0
        EOF
      duration = "0s"
    }
  }

  notification_channels = [
    # Nick Masson: SMS
    "projects/contrails-301217/notificationChannels/5296843968149494052",
    # Mahesh Saripalli: SMS 
    "projects/contrails-301217/notificationChannels/12238957771652159581",
  ]
}

#
# spire-cache-bot
#
resource "google_logging_metric" "spire_cache_bot_success_counter" {
  name = "spire-cache-bot-success-counter"
  filter = <<EOF
        resource.type="k8s_container"
        resource.labels.cluster_name="contrails-gke-general"
        resource.labels.namespace_name="flights-pipeline-prod"
        labels.k8s-pod/job-name:"spire-cache-bot-cronjob-"
        textPayload =~ "Successfully called API"
        EOF

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_monitoring_alert_policy" "k8cronjob_spire_cache_bot_success_count_below_threshold" {
  display_name = "k8scronjob-spire-cache-bot-success-count-below-threshold"
  combiner     = "OR"

  conditions {
    display_name = "success count is below threshold (1 per hour)"
    condition_monitoring_query_language {
      query    = <<EOF
        fetch k8s_container
        | metric 'logging.googleapis.com/user/${google_logging_metric.spire_cache_bot_success_counter.name}'
        | group_by [], sliding(70m)
        | every 1m
        | condition val() == 0
        EOF
      duration = "0s"
    }
  }

  notification_channels = [
    # Nick Masson: SMS
    "projects/contrails-301217/notificationChannels/5296843968149494052",
    # Mahesh Saripalli: SMS 
    "projects/contrails-301217/notificationChannels/12238957771652159581",
  ]
}

# 
# trajectory-worker-gaia
# 
resource "google_monitoring_alert_policy" "k8sdeployment_trajectory_worker_gaia_prod_error_in_logs" {
  display_name = "k8sdeployment-trajectory-worker-gaia-prod-error-in-logs"
  combiner     = "OR"

  conditions {
    display_name = "Error in logs"
    condition_matched_log {
      filter = <<EOF
        resource.type="k8s_container"
        resource.labels.cluster_name="contrails-gke-general"
        resource.labels.namespace_name="flights-pipeline-prod"
        labels.k8s-pod/app="trajectory-worker-gaia"
        severity>=ERROR
        jsonPayload.textPayload !~ "PERMANENT_FAILURE_INVALID_ACK_ID"
        EOF
    }
  }

  notification_channels = [
    # Nick Masson: SMS
    "projects/contrails-301217/notificationChannels/5296843968149494052",
    # Mahesh Saripalli: SMS 
    "projects/contrails-301217/notificationChannels/12238957771652159581",
  ]

  alert_strategy {
    notification_rate_limit {
      period = "3600s"
    }
    auto_close = "86400s"
  }
}

resource "google_logging_metric" "trajectory_worker_gaia_prod_ack_id_failure_counter" {
  name = "trajectory-worker-gaia-prod-ack-id-failure-counter"
  filter = <<EOF
        resource.type="k8s_container"
        resource.labels.cluster_name="contrails-gke-general"
        resource.labels.namespace_name="flights-pipeline-prod"
        labels.k8s-pod/app="trajectory-worker-gaia"
        severity>=ERROR
        jsonPayload.textPayload =~ "PERMANENT_FAILURE_INVALID_ACK_ID"
        EOF

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_monitoring_alert_policy" "k8sdeployment_trajectory_worker_gaia_prod_ack_id_failure_above_threshold" {
  display_name = "k8sdeployment-trajectory-worker-gaia-prod-ack-id-failure-above-threshold"
  combiner     = "OR"

  conditions {
    display_name = "ack id failure in logs; above threshold"
    condition_monitoring_query_language {
      query    = <<EOF
        fetch k8s_container
        | metric 'logging.googleapis.com/user/${google_logging_metric.trajectory_worker_gaia_prod_ack_id_failure_counter.name}'
        | group_by sliding(10m), aggregate(value.counter)
        | every 1m
        | condition val() > 5
        EOF
      duration = "0s"
    }
  }

  notification_channels = [
    # Nick Masson: SMS
    "projects/contrails-301217/notificationChannels/5296843968149494052",
    # Mahesh Saripalli: SMS 
    "projects/contrails-301217/notificationChannels/12238957771652159581",
  ]
}


resource "google_monitoring_alert_policy" "pubsubtopic_prod_gaia_trajectory_chunk_dead_letter_publish_count" {
  display_name = "pubsubtopic-${google_pubsub_topic.prod_gaia_trajectory_chunk_dead_letter.name}-publish-count"
  combiner     = "OR"

  conditions {
    display_name = "Publish count above threshold"
    condition_monitoring_query_language {
      query    = <<EOF
        fetch pubsub_topic
        | metric 'pubsub.googleapis.com/topic/message_sizes'
        | filter resource.topic_id == '${google_pubsub_topic.prod_gaia_trajectory_chunk_dead_letter.name}'
        | group_by sliding(30m), row_count()
        | every 1m
        | condition val() > 0
        EOF
      duration = "0s"
    }
  }

  notification_channels = [
    # Nick Masson: SMS
    "projects/contrails-301217/notificationChannels/5296843968149494052",
    # Mahesh Saripalli: SMS 
    "projects/contrails-301217/notificationChannels/12238957771652159581",
  ]
}

resource "google_monitoring_alert_policy" "pubsubtopic_prod_trajectory_worker_cocip_egress_bigquery_dead_letter_publish_count" {
  display_name = "pubsubtopic-${google_pubsub_topic.prod_trajectory_worker_cocip_egress_bigquery_dead_letter.name}-publish-count"
  combiner     = "OR"

  conditions {
    display_name = "Publish count above threshold"
    condition_monitoring_query_language {
      query    = <<EOF
        fetch pubsub_topic
        | metric 'pubsub.googleapis.com/topic/message_sizes'
        | filter resource.topic_id == '${google_pubsub_topic.prod_trajectory_worker_cocip_egress_bigquery_dead_letter.name}'
        | group_by sliding(30m), row_count()
        | every 1m
        | condition val() > 0
        EOF
      duration = "0s"
    }
  }

  notification_channels = [
    # Nick Masson: SMS
    "projects/contrails-301217/notificationChannels/5296843968149494052",
    # Mahesh Saripalli: SMS 
    "projects/contrails-301217/notificationChannels/12238957771652159581",
  ]
}

#
# flight-emissions-report (cron)
#
resource "google_monitoring_alert_policy" "k8scronjob_flight_emissions_report_cron_prod_error_in_logs" {
  display_name = "k8scronjob-flight-emissions-report-cron-prod-error-in-logs"
  combiner     = "OR"

  conditions {
    display_name = "Error in logs"
    condition_matched_log {
      filter = <<EOF
        resource.type="k8s_container"
        resource.labels.cluster_name="contrails-gke-general"
        resource.labels.namespace_name="flights-pipeline-prod"
        labels.k8s-pod/job-name:"flight-emissions-report-cronjob-"
        severity>=ERROR
        EOF
    }
  }

  notification_channels = [
    # Nick Masson: SMS
    "projects/contrails-301217/notificationChannels/5296843968149494052",
    # Mahesh Saripalli: SMS 
    "projects/contrails-301217/notificationChannels/12238957771652159581",
  ]

  alert_strategy {
    notification_rate_limit {
      period = "3600s"
    }
    auto_close = "86400s"
  }
}

resource "google_monitoring_alert_policy" "k8scronjob_flight_emissions_cron_report_non_zero_exit" {
  display_name = "k8scronjob-flight-emissions-report-non-zero-exit"
  combiner     = "OR"

  conditions {
    display_name = "failure; non-zero exit"
    condition_matched_log {
      filter = <<EOF
        log_id(cloudaudit.googleapis.com%2Factivity) resource.type=k8s_cluster
        resource.type=k8s_cluster protoPayload.resourceName=~"core/v1/namespaces/flights-pipeline-prod/pods/flight-emissions-report-cronjob"
        (protoPayload.response.status.containerStatuses.state.terminated.exitCode:*
          -protoPayload.response.status.containerStatuses.state.terminated.exitCode=0
        )
        EOF
    }
  }

  notification_channels = [
    # Nick Masson: SMS
    "projects/contrails-301217/notificationChannels/5296843968149494052",
    # Mahesh Saripalli: SMS 
    "projects/contrails-301217/notificationChannels/12238957771652159581",
  ]

  alert_strategy {
    notification_rate_limit {
      period = "3600s"
    }
    auto_close = "86400s"
  }
}

#
# trajectory-worker-job-factory
#
resource "google_monitoring_alert_policy" "k8sdeployment_trajectory_worker_job_factory_prod_error_in_logs" {
  display_name = "k8sdeployment-trajectory-worker-job-factory-prod-error-in-logs"
  combiner     = "OR"

  conditions {
    display_name = "Error in logs"
    condition_matched_log {
      filter = <<EOF
        resource.type="k8s_container"
        resource.labels.cluster_name="contrails-gke-general"
        resource.labels.namespace_name="flights-pipeline-prod"
        labels.k8s-pod/app="trajectory-worker-job-factory"
        severity>=ERROR
        jsonPayload.textPayload !~ "PERMANENT_FAILURE_INVALID_ACK_ID"
        EOF
    }
  }

  notification_channels = [
    # Nick Masson: SMS
    "projects/contrails-301217/notificationChannels/5296843968149494052",
    # Mahesh Saripalli: SMS 
    "projects/contrails-301217/notificationChannels/12238957771652159581",
  ]

  alert_strategy {
    notification_rate_limit {
      period = "3600s"
    }
    auto_close = "86400s"
  }
}

resource "google_monitoring_alert_policy" "pubsubtopic_prod_twjd_ingress_dead_letter_publish_count" {
  display_name = "pubsubtopic-${google_pubsub_topic.prod_twjd_ingress_dead_letter.name}-publish-count"
  combiner     = "OR"

  conditions {
    display_name = "Publish count above threshold"
    condition_monitoring_query_language {
      query    = <<EOF
        fetch pubsub_topic
        | metric 'pubsub.googleapis.com/topic/message_sizes'
        | filter resource.topic_id == '${google_pubsub_topic.prod_twjd_ingress_dead_letter.name}'
        | group_by sliding(30m), row_count()
        | every 1m
        | condition val() > 0
        EOF
      duration = "0s"
    }
  }

  notification_channels = [
    # Nick Masson: SMS
    "projects/contrails-301217/notificationChannels/5296843968149494052",
    # Mahesh Saripalli: SMS 
    "projects/contrails-301217/notificationChannels/12238957771652159581",
  ]
}

#
# nat-track-cacher
#
resource "google_monitoring_alert_policy" "k8scron_nat_track_cacher_prod_error_in_logs" {
  display_name = "k8scron-nat-track-cacher-prod-error-in-logs"
  combiner     = "OR"

  conditions {
    display_name = "Error in logs"
    condition_matched_log {
      filter = <<EOF
        resource.type="k8s_container"
        resource.labels.cluster_name="contrails-gke-general"
        resource.labels.namespace_name="flights-pipeline-prod"
        labels.k8s-pod/job-name:"nat-track-cacher"
        severity>=ERROR
        EOF
    }
  }

  notification_channels = [
    # Nick Masson: SMS
    "projects/contrails-301217/notificationChannels/5296843968149494052",
    # Mahesh Saripalli: SMS 
    "projects/contrails-301217/notificationChannels/12238957771652159581",
  ]

  alert_strategy {
    notification_rate_limit {
      period = "3600s"
    }
    auto_close = "86400s"
  }
}