# Free AI Gateway — task runner
# Author: Mourad Soltani — © 2026 Mourad Soltani Technologies™ @MST
.PHONY: help install run dev test test-health lint fmt clean docker docker-up docker-logs package stats health verify

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-14s %s\n", $$1, $$2}'

install:
	./install.sh

verify:
	./verify.sh

run:
	./run.sh

dev:
	./venv/bin/litellm --config config.yaml --port 4000 --num_workers 1 --detailed_debug

test:
	./venv/bin/pytest -q

test-health:
	./venv/bin/pytest -q tests/test_healthcheck.py

lint:
	./venv/bin/ruff check .

fmt:
	./venv/bin/ruff format .

clean:
	rm -rf __pycache__ tests/__pycache__ .pytest_cache .ruff_cache api_limits.db*
	find . -name '*.pyc' -delete

docker:
	docker build -t free-ai-gateway:latest .

docker-up:
	docker compose up -d --build

docker-logs:
	docker compose logs -f gateway

health:
	./venv/bin/python healthcheck.py --level full

stats:
	./venv/bin/python client.py --stats

package: clean
	cd .. && zip -r free-ai-gateway.zip free-ai-gateway \
	  -x "free-ai-gateway/venv/*" \
	     "free-ai-gateway/.env" \
	     "free-ai-gateway/__pycache__/*" \
	     "free-ai-gateway/**/__pycache__/*" \
	     "free-ai-gateway/api_limits.db*" \
	     "free-ai-gateway/.pytest_cache/*" \
	     "free-ai-gateway/.ruff_cache/*"
