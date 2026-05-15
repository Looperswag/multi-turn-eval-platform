.PHONY: dev up down logs seed migrate fmt test

dev:
	docker compose up --build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f api worker web

migrate:
	docker compose exec api alembic upgrade head

seed:
	docker compose exec api python -m app.seeds.seed

fmt:
	docker compose exec api ruff format app
	docker compose exec web npm run format

test:
	docker compose exec api pytest -q
