up:
	RAND=$$(openssl rand -base64 24 | tr -d '\n' | tr '/+' 'AZ') \
	envsubst < .env.example > .env
	COMPOSE_BAKE=true docker compose up -d --build

down:
	docker compose down
