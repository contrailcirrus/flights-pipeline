.PHONY: deploy
deploy: --check-env
	helm upgrade --install trajectory-worker-deployment . \
		--namespace=$(NAMESPACE) \
		--set image=$(IMAGE) \
		--set logLevel=$(LOG_LEVEL) \
		--set trajectoryChunkRealtimeSubscriptionId=$(TRAJECTORY_CHUNK_REALTIME_SUBSCRIPTION_ID) \
		--set trajectoryChunkBatchSubscriptionId=$(TRAJECTORY_CHUNK_REALTIME_SUBSCRIPTION_ID) \
		--set hresSourcePath=$(HRES_SOURCE_PATH) \
		--set gitSha=$(GIT_SHA) \
		--set trajectoryCocipBqTopicId=$(TRAJECTORY_COCIP_BQ_TOPIC_ID)

.PHONY: --check-env
--check-env:
	@test $${NAMESPACE?environment variable is required}
	@test $${IMAGE?environment variable is required}
	@test $${LOG_LEVEL?environment variable is required}
	@test $${TRAJECTORY_CHUNK_REALTIME_SUBSCRIPTION_ID?environment variable is required}
	@test $${TRAJECTORY_CHUNK_BATCH_SUBSCRIPTION_ID?environment variable is required}
	@test $${HRES_SOURCE_PATH?environment variable is required}
	@test $${GIT_SHA?environment variable is required}
	@test $${TRAJECTORY_COCIP_BQ_TOPIC_ID?environment variable is required}
