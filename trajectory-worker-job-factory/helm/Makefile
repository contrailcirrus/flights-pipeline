.PHONY: deploy
deploy: --check-env
	helm upgrade --install trajectory-worker-job-factory-deployment . \
		--namespace=$(NAMESPACE) \
		--set image=$(IMAGE) \
		--set logLevel=$(LOG_LEVEL) \
		--set twjdSubscriptionId=$(TWJD_SUBSCRIPTION_ID) \
		--set trajectoryChunkTopicId=$(TRAJECTORY_CHUNK_TOPIC_ID) \
		--set redisHost=$(REDIS_HOST) \
		--set redisPort=$(REDIS_PORT)

.PHONY: --check-env
--check-env:
	@test $${NAMESPACE?environment variable is required}
	@test $${IMAGE?environment variable is required}
	@test $${LOG_LEVEL?environment variable is required}
	@test $${TWJD_SUBSCRIPTION_ID?environment variable is required}
	@test $${TRAJECTORY_CHUNK_TOPIC_ID?environment variable is required}
	@test $${REDIS_HOST?environment variable is required}
	@test $${REDIS_PORT?environment variable is required}