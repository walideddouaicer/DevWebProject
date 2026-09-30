PY ?= .venv/bin/python
RUFF ?= .venv/bin/ruff
MANAGE = $(PY) manage.py
# Throwaway prod-like env used only for `check --deploy`.
DEPLOY_ENV = DJANGO_DEBUG=False ENVIRONMENT=prod \
	DJANGO_SECRET_KEY=check-deploy-only-0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJ \
	DJANGO_ALLOWED_HOSTS=example.com SITE_URL=https://example.com EMAIL_HOST=smtp.example.com \
	DATABASE_URL=postgres://u:p@localhost:5432/db

.PHONY: setup run demo demo-reset test e2e lint format check coverage screens qa seed docker-build docker-up

setup:
	python3 -m venv .venv
	.venv/bin/pip install -q --upgrade pip
	.venv/bin/pip install -q -r requirements/dev.txt
	$(MANAGE) migrate

run:
	$(MANAGE) runserver

test:
	$(MANAGE) test --parallel auto --exclude-tag e2e

# Browser end-to-end journeys (Playwright + live server), see e2e/
e2e:
	$(MANAGE) test e2e --tag e2e

lint:
	$(RUFF) check .
	$(RUFF) format --check .

format:
	$(RUFF) format .
	$(RUFF) check --fix .

check: lint
	$(MANAGE) check --fail-level WARNING
	$(DEPLOY_ENV) $(MANAGE) check --deploy --fail-level WARNING
	$(MANAGE) makemigrations --check --dry-run
	$(MANAGE) test --parallel auto --exclude-tag e2e

coverage:
	.venv/bin/coverage run manage.py test
	.venv/bin/coverage report --skip-covered --sort=cover

seed:
	$(MANAGE) seed_demo

# Demo instance for presentations: its own database and uploads in $(DEMO_DIR) (never the
# project's db.sqlite3), demo accounts loaded on first run, emails printed in the terminal.
#   make demo         start it (keeps whatever you did in it last time)
#   make demo-reset   start again from fresh demo data
DEMO_DIR ?= $(HOME)/.ensa-demo
DEMO_ENV = DJANGO_DEBUG=True DATABASE_URL=sqlite:///$(DEMO_DIR)/db.sqlite3 \
	MEDIA_ROOT=$(DEMO_DIR)/media PRIVATE_MEDIA_ROOT=$(DEMO_DIR)/private \
	SCHEDULER_STATE_FILE=$(DEMO_DIR)/scheduler.json
demo:
	@mkdir -p $(DEMO_DIR)
	@if [ ! -f $(DEMO_DIR)/db.sqlite3 ]; then \
		$(DEMO_ENV) $(MANAGE) migrate -v0 && $(DEMO_ENV) $(MANAGE) seed_demo; \
	else $(DEMO_ENV) $(MANAGE) migrate -v0; fi
	@echo "Demo: http://127.0.0.1:8000 — accounts admin, prof.alami, etu.youssef… password demo12345!"
	$(DEMO_ENV) $(MANAGE) runserver 127.0.0.1:8000

demo-reset:
	rm -rf $(DEMO_DIR)
	$(MAKE) demo

screens:
	$(PY) scripts/screens.py $(ARGS)

# Browser QA: every page x role under the enforced CSP; fails on console errors,
# CSP violations or serious/critical axe issues.
qa:
	$(PY) scripts/screens.py --strict --themes light

docker-build:
	docker build -t ensa-project-manager .

docker-up:
	docker compose up --build
