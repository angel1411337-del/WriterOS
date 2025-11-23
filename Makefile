.PHONY: build up down test clean

build:
	docker build -f docker/Dockerfile -t writeros:latest .

up:
	docker-compose -f docker/docker-compose.yml up --build

down:
	docker-compose -f docker/docker-compose.yml down

test:
	pytest tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
