.PHONY: deploy
deploy: --check-env
	helm upgrade --install spire-ingest-resample-worker . \
		--namespace=$(NAMESPACE) \
		--set image=$(IMAGE) \
		--set trajectoryChunkSubscriptionId=$(TRAJECTORY_CHUNK_SUBSCRIPTION_ID)

.PHONY: --check-env
--check-env:
	@test $${NAMESPACE?environment variable is required}
	@test $${IMAGE?environment variable is required}
	@test $${TRAJECTORY_CHUNK_SUBSCRIPTION_ID?environment variable is required}
