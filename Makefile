up:
	COMPOSE_BAKE=true docker compose up -d --build

down:
	docker compose down

dev:
	docker compose watch

fmtdc:
	yq -i -P 'sort_keys(..)' compose.yaml
	bunx dclint . --fix
