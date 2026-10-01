ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PYTHON := python3

.PHONY: dev db-stop check generate-client test-integration test-e2e test-faults

dev:
	$(PYTHON) "$(ROOT)/scripts/verify.py" dev

db-stop:
	docker compose --project-name yudada-next --file "$(ROOT)/compose.yml" stop db

check:
	$(PYTHON) "$(ROOT)/scripts/verify.py" check

generate-client:
	$(PYTHON) "$(ROOT)/scripts/verify.py" generate

test-integration:
	$(PYTHON) "$(ROOT)/scripts/verify.py" integration

test-e2e:
	$(PYTHON) "$(ROOT)/scripts/verify.py" e2e

test-faults:
	$(PYTHON) "$(ROOT)/scripts/verify.py" faults
