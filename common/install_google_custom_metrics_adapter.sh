#!/bin/bash
#
# This script configures the Google Custom Metrics Adapter within the active
# Kubernetes cluster. The goal is to support Stackdriver-based external metrics
# for HorizontalPodAutoscalers.

# Auth current user as GKE cluster admin. Required to install custom metrics adapter.
kubectl create clusterrolebinding cluster-admin-binding \
    --clusterrole cluster-admin \
    --user "$(gcloud config get-value account)"

# Install custom metrics adapter resources into custom-metrics namespace.
RESOURCE_URI=https://raw.githubusercontent.com/GoogleCloudPlatform/k8s-stackdriver/master/custom-metrics-stackdriver-adapter/deploy/production/adapter_new_resource_model.yaml
kubectl apply -f $RESOURCE_URI

# See: https://github.com/GoogleCloudPlatform/k8s-stackdriver/blob/master/custom-metrics-stackdriver-adapter
# We auth the default compute engine service account, which is currently used
# as the default service account for the contrails-gke-general cluster.
#
# The service account must be bound to the `roles/monitoring.viewer` role and
# support workload identity federation via `roles/iam.workloadIdentityUser` to
# grant access to the custom-metrics service account. Auth for Google service
# accounts is currently set up in .cloud/auth.tf
SERVICE_ACCOUNT=577335432373-compute@developer.gserviceaccount.com
kubectl annotate serviceaccount --namespace custom-metrics \
    custom-metrics-stackdriver-adapter \
    iam.gke.io/gcp-service-account=$SERVICE_ACCOUNT
