PYTHON ?= $(if $(wildcard .venv/ops/bin/python),.venv/ops/bin/python,$(if $(wildcard .venv/bin/python),.venv/bin/python,python3))
ENV_FILE ?=
OPS_ENV_FILE ?=
APPROVAL_FILE ?=
TASK = $(PYTHON) scripts/ops/tasks.py
MANAGE = $(PYTHON) scripts/ops/manage.py

.PHONY: bootstrap dev lint typecheck test test-integration test-e2e test-inference test-visual build demo-static demo-full-up demo-full-down demo-reset diagrams diagrams-check docs-check prod-config-check ops-check verify audit role-init role-grants test-roles preflight infra-up storage-init migrate deploy rollback smoke backup restore

bootstrap lint typecheck test test-integration test-e2e test-inference test-visual build demo-static diagrams diagrams-check:
	$(TASK) $@
dev:
	$(MANAGE) dev --env-file "$(ENV_FILE)"

demo-full-up:
	$(MANAGE) demo-up --env-file "$(ENV_FILE)"
demo-full-down:
	$(MANAGE) demo-down --env-file "$(ENV_FILE)"
demo-reset:
	$(PYTHON) scripts/ops/data.py reset --env-file "$(OPS_ENV_FILE)" --quiesced
.PHONY: demo-seed test-demo-seed
demo-seed:
	$(PYTHON) scripts/ops/seed.py --env-file "$(OPS_ENV_FILE)" --date "$(SEED_DATE)"
test-demo-seed:
	$(PYTHON) scripts/check_demo_seed.py
docs-check:
	$(PYTHON) scripts/check_docs.py
prod-config-check:
	$(PYTHON) scripts/check_compose.py --env-file "$(ENV_FILE)"
ops-check:
	$(PYTHON) scripts/check_compose.py --self-test
	$(PYTHON) scripts/check_workflows.py
	$(PYTHON) -m unittest discover -s scripts/ops/tests -v
verify:
	$(TASK) verify
audit:
	$(PYTHON) scripts/ops/audit.py
role-init role-grants:
	$(PYTHON) scripts/ops/roles.py $@ --env-file "$(ENV_FILE)" --admin-env-file "$(ADMIN_ENV_FILE)"
test-roles:
	$(PYTHON) scripts/check_roles.py

preflight infra-up storage-init migrate smoke:
	$(MANAGE) $@ --env-file "$(ENV_FILE)"
deploy rollback:
	$(MANAGE) $@ --env-file "$(ENV_FILE)" --approval-file "$(APPROVAL_FILE)"
backup:
	$(PYTHON) scripts/ops/data.py backup --env-file "$(OPS_ENV_FILE)" --config-file "$(ENV_FILE)" --quiesced --evidence "$(EVIDENCE)"
restore:
	$(PYTHON) scripts/ops/data.py restore --env-file "$(OPS_ENV_FILE)" --quiesced --snapshot "$(SNAPSHOT)" --evidence "$(EVIDENCE)"
