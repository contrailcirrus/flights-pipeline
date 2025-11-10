.PHONY: deploy
deploy: --check-env
	helm upgrade --install spire-raw-batch . \
		--namespace=$(NAMESPACE) \
		--set image=$(IMAGE) \
		--set firestoreStateDb=$(FIRESTORE_STATE_DB) \
		--set firestoreStateCollection=$(FIRESTORE_STATE_COLLECTION) \
		--set firestoreStateDocId=$(FIRESTORE_STATE_DOC_ID) \
		--set gcsBucketName=$(GCS_BUCKET_NAME) \
		--set logLevel=$(LOG_LEVEL) \
		--set suspendCronjob=$(SUSPEND_CRONJOB)

.PHONY: --check-env
--check-env:
	@test $${NAMESPACE?environment variable is required}
	@test $${IMAGE?environment variable is required}
	@test $${FIRESTORE_STATE_DB?environment variable is required}
	@test $${FIRESTORE_STATE_COLLECTION?environment variable is required}
	@test $${FIRESTORE_STATE_DOC_ID?environment variable is required}
	@test $${GCS_BUCKET_NAME?environment variable is required}
	@test $${LOG_LEVEL?environment variable is required}
	@test $${SUSPEND_CRONJOB?environment variable is required}