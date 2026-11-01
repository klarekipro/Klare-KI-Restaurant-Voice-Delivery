PY := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: venv install run test seed reset-db

venv:
	python3 -m venv .venv

install: venv
	$(PIP) install -r requirements.txt

run:
	$(PY) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

seed:
	$(PY) -m app.seed

test:
	$(PY) -m pytest

reset-db:
	rm -f data/mvp.sqlite data/mvp.sqlite-wal data/mvp.sqlite-shm
