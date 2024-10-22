.PHONY: deploy
deploy: --check-env
	helm upgrade --install spire-ingest-resample-worker . \
		--namespace=$(NAMESPACE) \
		--set image=$(IMAGE) \
		--set logLevel=$(LOG_LEVEL) \
		--set spireIngestWaypointsSubscriptionId=$(SPIRE_INGEST_WAYPOINTS_SUBSCRIPTION_ID) \
		--set spireRawWaypointsBigQueryTopicId=$(SPIRE_RAW_WAYPOINTS_BIGQUERY_TOPIC_ID) \
		--set spireWaypointsBigQueryTopicId=$(SPIRE_WAYPOINTS_BIGQUERY_TOPIC_ID) \
		--set redisHost=$(REDIS_HOST) \
		--set redisPort=$(REDIS_PORT)

.PHONY: --check-env
--check-env:
	@test $${NAMESPACE?environment variable is required}
	@test $${IMAGE?environment variable is required}
	@test $${LOG_LEVEL?environment variable is required}
	@test $${SPIRE_INGEST_WAYPOINTS_SUBSCRIPTION_ID?environment variable is required}
	@test $${SPIRE_RAW_WAYPOINTS_BIGQUERY_TOPIC_ID?environment variable is required}
	@test $${SPIRE_WAYPOINTS_BIGQUERY_TOPIC_ID?environment variable is required}
	@test $${REDIS_HOST?environment variable is required}
	@test $${REDIS_PORT?environment variable is required}
