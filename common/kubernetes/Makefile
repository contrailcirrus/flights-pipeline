.PHONY: deploy
deploy: --check-env
	helm upgrade --install spire-ingest-api-scraper . \
		--namespace=$(NAMESPACE) \
		--set spireAirsafeApiToken=$(SPIRE_AIRSAFE_API_TOKEN)

.PHONY: --check-env
--check-env:
	@test $${NAMESPACE?environment variable is required}
	@test $${SPIRE_AIRSAFE_API_TOKEN?environment variable is required}
