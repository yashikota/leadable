up:
	COMPOSE_BAKE=true docker compose up -d --build
	echo "Server running at http://$(grep "^SERVER_ADDRESS=" .env | cut -d '=' -f2 | tr -d '"'):8877"

down:
	docker compose down

dev:
	docker compose watch

fmtdc:
	yq -i -P 'sort_keys(..)' compose.yaml
	bunx dclint . --fix

check:
	cd frontend && pnpm check && cd -
	cd backend && uv run task check && cd -
