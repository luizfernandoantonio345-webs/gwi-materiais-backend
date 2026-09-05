.PHONY: install dev test test-cov lint fmt migrate seed run docker security precommit

install:
	pip install -r requirements.txt

dev: install
	pip install ruff bandit pip-audit pre-commit
	pre-commit install

run:
	uvicorn app.main:app --reload

migrate:
	python -m alembic upgrade head

seed:
	python -m app.seed

test:
	python -m pytest -v

test-cov:
	python -m pytest --cov --cov-config=.coveragerc --cov-report=term-missing --cov-fail-under=70

lint:
	ruff check .
	ruff format --check .

fmt:
	ruff check . --fix
	ruff format .

security:
	bandit -r app -x app/seed.py --severity-level medium
	pip-audit -r requirements.txt

docker:
	docker build -t gwi-materiais-api .

precommit:
	pre-commit run --all-files
