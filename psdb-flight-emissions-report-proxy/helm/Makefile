.PHONY: deploy
deploy: --check-env
	helm upgrade --install psdb-flight-emissions-report-proxy . \
		--namespace=$(NAMESPACE) \
		--set psdbConnectionName=$(PSDB_CONNECTION_NAME)


.PHONY: --check-env
--check-env:
	@test $${NAMESPACE?environment variable is required}
	@test $${PSDB_CONNECTION_NAME?environment variable is required}
