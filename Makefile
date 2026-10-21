.PHONY: help backend-lint backend-test frontend-lint frontend-build frontend-test ci

help:
	@echo "backend-lint    ruff over app/tests/migrations"
	@echo "backend-test    schema + RLS + API tests (needs local Postgres)"
	@echo "frontend-lint   oxlint"
	@echo "frontend-build  typecheck + vite build"
	@echo "frontend-test   vitest (Jalali utilities)"
	@echo "ci              everything CI runs, in order"

backend-lint:
	cd backend && uv run ruff check app tests migrations

backend-test:
	cd backend && uv run pytest -q

frontend-lint:
	# npx (rather than `npm run lint`) so the raw exit code reaches us
	cd frontend && npx oxlint

frontend-build:
	cd frontend && npm run build

frontend-test:
	cd frontend && npm test

ci: backend-lint backend-test frontend-lint frontend-build frontend-test
	@echo "CI suite green."
