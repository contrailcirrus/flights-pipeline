.PHONY: deploy
deploy: --check-env
	helm upgrade --install flight-emissions-report . \
		--namespace=$(NAMESPACE) \
		--set image=$(IMAGE) \
		--set logLevel=$(LOG_LEVEL) \
		--set trajectoryWorkerTopic=$(TRAJECTORY_WORKER_TOPIC) \
		--set suspendCronjob=$(SUSPEND_CRONJOB)

.PHONY: --check-env
--check-env:
	@test $${NAMESPACE?environment variable is required}
	@test $${IMAGE?environment variable is required}
	@test $${LOG_LEVEL?environment variable is required}
	@test $${TRAJECTORY_WORKER_TOPIC?environment variable is required}
	@test $${SUSPEND_CRONJOB?environment variable is required}