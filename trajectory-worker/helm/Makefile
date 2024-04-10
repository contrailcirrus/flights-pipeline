.PHONY: deploy
deploy: --check-env
	helm upgrade --install trajectory-worker-deployment . \
		--namespace=$(NAMESPACE) \
		--set image=$(IMAGE) \
		--set trajectoryChunkSubscriptionId=$(TRAJECTORY_CHUNK_SUBSCRIPTION_ID) \
		--set hresSourcePath=$(HRES_SOURCE_PATH)

.PHONY: --check-env
--check-env:
	@test $${NAMESPACE?environment variable is required}
	@test $${IMAGE?environment variable is required}
	@test $${TRAJECTORY_CHUNK_SUBSCRIPTION_ID?environment variable is required}
	@test $${HRES_SOURCE_PATH?environment variable is required}
