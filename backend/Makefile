.PHONY: help install dev test test-random test-v test-changed test-cov lint format typecheck check jj-server docker-build docker-up docker-down clean test-with-jj test-jj-up test-jj-down

help:
	@echo "Available commands:"
	@echo "  make install      - Install dependencies"
	@echo "  make dev          - Run with hot reload"
	@echo "  make test         - Run all Vedro tests"
	@echo "  make test-random  - Run tests in random order"
	@echo "  make test-v       - Run tests verbose"
	@echo "  make test-changed - Run tests for changed files"
	@echo "  make test-cov     - Run tests with coverage report"
	@echo "  make jj-server    - Start JJ mock server for testing"
	@echo "  make test-with-jj - Run tests in Docker with JJ mock server"
	@echo "  make test-jj-up   - Start JJ mock server container"
	@echo "  make test-jj-down - Stop JJ mock server container"
	@echo "  make lint         - Run ruff linter"
	@echo "  make format       - Format code with ruff"
	@echo "  make typecheck    - Run mypy type checker"
	@echo "  make check        - Run all checks (lint + typecheck)"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-up    - Start Docker containers"
	@echo "  make docker-down  - Stop Docker containers"
	@echo "  make clean        - Clean cache files"

install:
	uv sync

dev:
	./scripts/dev.sh

test:
	uv run vedro run scenarios/ -f

test-random:
	uv run vedro run scenarios/ --order-random

test-v:
	uv run vedro run scenarios/ -v

test-changed:
	uv run vedro run scenarios/ --changed-against-branch=main

test-cov:
	uv run coverage run -m vedro run scenarios/
	uv run coverage report -m
	uv run coverage html

jj-server:
	./scripts/start_jj.sh

lint:
	uv run ruff check src/ scenarios/

format:
	uv run ruff format src/ scenarios/

typecheck:
	uv run mypy src/

check: lint typecheck

docker-build:
	cd ../docker && docker compose build

docker-up:
	cd ../docker && docker compose up -d

docker-down:
	cd ../docker && docker compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf htmlcov/ .coverage 2>/dev/null || true

# Docker-based testing with JJ Mock Server
test-with-jj:
	docker compose -f ../docker/docker-compose.test.yml up --build --abort-on-container-exit

test-jj-up:
	docker compose -f ../docker/docker-compose.test.yml up -d jj-mock

test-jj-down:
	docker compose -f ../docker/docker-compose.test.yml down
