.PHONY: deploy
deploy: --check-env
	helm upgrade --install spire-ingest-api-scraper . \
		--namespace=$(NAMESPACE) \
		--set image=$(IMAGE) \
		--set firestoreStateDb=$(FIRESTORE_STATE_DB) \
		--set firestoreStateCollection=$(FIRESTORE_STATE_COLLECTION) \
		--set firestoreStateDocId=$(FIRESTORE_STATE_DOC_ID) \
		--set spireRawWaypointsBigQueryTopicId=$(SPIRE_RAW_WAYPOINTS_BIGQUERY_TOPIC_ID) \
		--set pubSubEgressTopicId=$(PUBSUB_EGRESS_TOPIC_ID) \
		--set-string suspendCronjob=$(SUSPEND_CRONJOB)

.PHONY: --check-env
--check-env:
	@test $${NAMESPACE?environment variable is required}
	@test $${IMAGE?environment variable is required}
	@test $${FIRESTORE_STATE_DB?environment variable is required}
	@test $${FIRESTORE_STATE_COLLECTION?environment variable is required}
	@test $${FIRESTORE_STATE_DOC_ID?environment variable is required}
	@test $${PUBSUB_EGRESS_TOPIC_ID?environment variable is required}
	@test $${SPIRE_RAW_WAYPOINTS_BIGQUERY_TOPIC_ID?environment variable is required}
	@test $${SUSPEND_CRONJOB?environment variable is required}
