up:
	docker compose -f infra/compose/docker-compose.yml up --build

down:
	docker compose -f infra/compose/docker-compose.yml down
