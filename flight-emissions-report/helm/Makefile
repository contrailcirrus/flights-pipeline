.PHONY: deploy
deploy: --check-env
	helm upgrade --install flight-emissions-report . \
		--namespace=$(NAMESPACE) \
		--set image=$(IMAGE) \
		--set logLevel=$(LOG_LEVEL) \
		--set twjdTopicId=$(TWJD_TOPIC_ID) \
		--set suspendCronjob=$(SUSPEND_CRONJOB)

.PHONY: --check-env
--check-env:
	@test $${NAMESPACE?environment variable is required}
	@test $${IMAGE?environment variable is required}
	@test $${LOG_LEVEL?environment variable is required}
	@test $${TWJD_TOPIC_ID?environment variable is required}
	@test $${SUSPEND_CRONJOB?environment variable is required}