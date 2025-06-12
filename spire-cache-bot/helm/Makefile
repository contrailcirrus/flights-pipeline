.PHONY: deploy
deploy:
	helm upgrade --install spire-cache-bot . \
		--namespace=$(NAMESPACE) \
		--set image=$(IMAGE) \
		--set suspendCronjob=$(SUSPEND_CRONJOB)