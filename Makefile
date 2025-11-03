.PHONY: dev up down logs build test lint typecheck redis-flush postfix-logs

dev:
	uvicorn api.main:app --reload --port 8000

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

test:
	pytest tests/ -v -m "not network"

test-all:
	pytest tests/ -v

lint:
	ruff check api/ parser/ tests/

typecheck:
	mypy api/ parser/

redis-flush:
	docker compose exec redis redis-cli FLUSHDB

postfix-logs:
	docker compose logs -f postfix
