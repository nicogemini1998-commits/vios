.PHONY: setup up down health test migrate lint

setup:
	@echo "$(CURDIR)" | grep -qi onedrive && { echo "ABORT: repo no puede vivir en OneDrive (EDEADLK)"; exit 1; } || true
	@echo "OK: ruta segura"

up:
	docker compose up -d --build

down:
	docker compose down

migrate:
	docker compose exec -T db psql -U vios -d vios < db/migrations/0001_init.sql

health:
	cd apps/engine && uv run vios health

test:
	cd apps/engine && uv run pytest -q
