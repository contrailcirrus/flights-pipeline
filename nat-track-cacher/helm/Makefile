.PHONY: deploy
deploy: --check-env
	helm upgrade --install nat-track-cacher . \
		--namespace=$(NAMESPACE) \
		--set image=$(IMAGE) \
		--set logLevel=$(LOG_LEVEL) \
		--set natTrackApiUrl=$(NAT_TRACK_API_URL) \
		--set bqTableId=$(BQ_TABLE_ID) \
		--set suspendCronjob=$(SUSPEND_CRONJOB)

.PHONY: --check-env
--check-env:
	@test $${NAMESPACE?environment variable is required}
	@test $${IMAGE?environment variable is required}
	@test $${LOG_LEVEL?environment variable is required}
	@test $${NAT_TRACK_API_URL?environment variable is required}
	@test $${BQ_TABLE_ID?environment variable is required}
	@test $${SUSPEND_CRONJOB?environment variable is required}