# 
# api-scraper
# 
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

resource "google_monitoring_alert_policy" "pubsubtopic_prod_api_scraper_egress_publish_count" {
  display_name = "pubsubtopic-${google_pubsub_topic.prod_api_scraper_egress.name}-publish-count"
  combiner     = "OR"

  conditions {
    display_name = "Publish count below threshold"
    condition_monitoring_query_language {
      query    = <<EOF
        fetch pubsub_topic
        | metric 'pubsub.googleapis.com/topic/message_sizes'
        | filter resource.topic_id == '${google_pubsub_topic.prod_api_scraper_egress.name}'
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
  ]
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
  ]
}

resource "google_monitoring_alert_policy" "pubsubtopic_prod_api_scraper_bigquery_egress_dead_letter_publish_count" {
  display_name = "pubsubtopic-${google_pubsub_topic.prod_spire_ingest_raw_bigquery.name}-publish-count"
  combiner     = "OR"

  conditions {
    display_name = "Publish count above threshold"
    condition_monitoring_query_language {
      query    = <<EOF
        fetch pubsub_topic
        | metric 'pubsub.googleapis.com/topic/message_sizes'
        | filter resource.topic_id == '${google_pubsub_topic.prod_spire_ingest_raw_bigquery.name}'
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
  ]
}


# 
# resample-worker
# 
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

resource "google_monitoring_alert_policy" "pubsubsubscription_prod_resample_worker_ingress_ack_count" {
  display_name = "pubsubsubscription-${google_pubsub_subscription.prod_resample_worker_ingress.name}-ack-count"
  combiner     = "OR"

  conditions {
    display_name = "Subscriber ack count below threshold"
    condition_monitoring_query_language {
      query    = <<EOF
        fetch pubsub_subscription
        | metric 'pubsub.googleapis.com/subscription/ack_message_count'
        | filter resource.subscription_id == '${google_pubsub_subscription.prod_resample_worker_ingress.name}'
        | group_by sliding(30m), aggregate(value.ack_message_count)
        | every 1m
        | condition val() < 10
        EOF
      duration = "0s"
    }
  }

  notification_channels = [
    # Nick Masson: SMS
    "projects/contrails-301217/notificationChannels/5296843968149494052",
  ]
}

resource "google_monitoring_alert_policy" "pubsubsubscription_prod_resample_worker_ingress_oldest_message" {
  display_name = "pubsubsubscription-${google_pubsub_subscription.prod_resample_worker_ingress.name}-oldest-message"
  combiner     = "OR"

  conditions {
    display_name = "Oldest unacked message above threshold"
    condition_monitoring_query_language {
      query    = <<EOF
        fetch pubsub_subscription
        | metric 'pubsub.googleapis.com/subscription/oldest_unacked_message_age'
        | filter resource.subscription_id == '${google_pubsub_subscription.prod_resample_worker_ingress.name}'
        | window 10m
        | every 1m
        | condition value.oldest_unacked_message_age > cast_units(3600, "s")
        EOF
      duration = "0s"
    }
  }

  notification_channels = [
    # Nick Masson: SMS
    "projects/contrails-301217/notificationChannels/5296843968149494052",
  ]
}

resource "google_monitoring_alert_policy" "pubsubtopic_prod_resample_worker_egress_publish_count" {
  display_name = "pubsubtopic-${google_pubsub_topic.prod_resample_worker_trajectory_chunk_egress.name}-publish-count"
  combiner     = "OR"

  conditions {
    display_name = "Publish count below threshold"
    condition_monitoring_query_language {
      query    = <<EOF
        fetch pubsub_topic
        | metric 'pubsub.googleapis.com/topic/message_sizes'
        | filter resource.topic_id == '${google_pubsub_topic.prod_resample_worker_trajectory_chunk_egress.name}'
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
  ]
}

resource "google_monitoring_alert_policy" "pubsubtopic_prod_resample_worker_ingress_dead_letter_publish_count" {
  display_name = "pubsubtopic-${google_pubsub_topic.prod_resample_worker_ingress_dead_letter.name}-publish-count"
  combiner     = "OR"

  conditions {
    display_name = "Publish count above threshold"
    condition_monitoring_query_language {
      query    = <<EOF
        fetch pubsub_topic
        | metric 'pubsub.googleapis.com/topic/message_sizes'
        | filter resource.topic_id == '${google_pubsub_topic.prod_resample_worker_ingress_dead_letter.name}'
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
  ]
}

resource "google_monitoring_alert_policy" "pubsubtopic_prod_resample_worker_bigquery_egress_dead_letter_publish_count" {
  display_name = "pubsubtopic-${google_pubsub_topic.prod_spire_ingest_resampled_bigquery_dead_letter.name}-publish-count"
  combiner     = "OR"

  conditions {
    display_name = "Publish count above threshold"
    condition_monitoring_query_language {
      query    = <<EOF
        fetch pubsub_topic
        | metric 'pubsub.googleapis.com/topic/message_sizes'
        | filter resource.topic_id == '${google_pubsub_topic.prod_spire_ingest_resampled_bigquery_dead_letter.name}'
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
  ]
}

# 
# trajectory-worker
# 
# TODO: enable trajectory-worker alerts after prod deployment
# resource "google_monitoring_alert_policy" "k8sdeployment_trajectory_worker_realtime_prod_error_in_logs" {
#   display_name = "k8sdeployment-trajectory-worker-realtime-prod-error-in-logs"
#   combiner     = "OR"

#   conditions {
#     display_name = "Error in logs"
#     condition_matched_log {
#       filter = <<EOF
#         resource.type="k8s_container"
#         resource.labels.cluster_name="contrails-gke-general"
#         resource.labels.namespace_name="flights-pipeline-prod"
#         labels.k8s-pod/app="trajectory-worker-realtime"
#         severity>=ERROR
#         EOF
#     }
#   }

#   notification_channels = [
#     # Nick Masson: SMS
#     "projects/contrails-301217/notificationChannels/5296843968149494052",
#   ]

#   alert_strategy {
#     notification_rate_limit {
#       period = "3600s"
#     }
#     auto_close = "86400s"
#   }
# }

# resource "google_monitoring_alert_policy" "k8sdeployment_trajectory_worker_batch_prod_error_in_logs" {
#   display_name = "k8sdeployment-trajectory-worker-batch-prod-error-in-logs"
#   combiner     = "OR"

#   conditions {
#     display_name = "Error in logs"
#     condition_matched_log {
#       filter = <<EOF
#         resource.type="k8s_container"
#         resource.labels.cluster_name="contrails-gke-general"
#         resource.labels.namespace_name="flights-pipeline-prod"
#         labels.k8s-pod/app="trajectory-worker-batch"
#         severity>=ERROR
#         EOF
#     }
#   }

#   notification_channels = [
#     # Nick Masson: SMS
#     "projects/contrails-301217/notificationChannels/5296843968149494052",
#   ]

#   alert_strategy {
#     notification_rate_limit {
#       period = "3600s"
#     }
#     auto_close = "86400s"
#   }
# }
