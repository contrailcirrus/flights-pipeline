.PHONY: deploy
deploy:
	helm upgrade --install trajectory-worker-deployment . \
		--namespace=$(NAMESPACE) \
		--set image=$(IMAGE) \
		--set logLevel=$(LOG_LEVEL) \
		--set trajectoryChunkGaiaSubscriptionId=$(TRAJECTORY_CHUNK_GAIA_SUBSCRIPTION_ID) \
		--set trajectoryChunkGaiaBackupTopicId=$(TRAJECTORY_CHUNK_GAIA_BACKUP_TOPIC_ID) \
		--set trajectoryChunkGaiaBackupSubscriptionId=$(TRAJECTORY_CHUNK_GAIA_BACKUP_SUBSCRIPTION_ID) \
		--set hresSourcePath=$(HRES_SOURCE_PATH) \
		--set era5SourcePath=$(ERA5_SOURCE_PATH) \
		--set gitSha=$(GIT_SHA) \
		--set trajectoryCocipBqTopicId=$(TRAJECTORY_COCIP_BQ_TOPIC_ID) \
