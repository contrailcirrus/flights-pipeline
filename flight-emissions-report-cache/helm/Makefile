.PHONY: deploy
deploy: --check-env
	helm upgrade --install flight-emissions-report-cache . \
		--namespace=$(NAMESPACE) \
		--set image=$(IMAGE) \
		--set logLevel=$(LOG_LEVEL) \
		--set psdbUser=$(PSDB_USER) \
		--set suspendCronjob=$(SUSPEND_CRONJOB)



.PHONY: --check-env
--check-env:
	@test $${NAMESPACE?environment variable is required}
	@test $${IMAGE?environment variable is required}
	@test $${LOG_LEVEL?environment variable is required}
	@test $${PSDB_USER?environment variable is required}
	@test $${PSDB_HOST?environment variable is required}
	@test $${SUSPEND_CRONJOB?environment variable is required}

