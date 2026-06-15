PYTHON = python
PIP = pip

.PHONY: install migrate sprite run setup audit

install:
	$(PIP) install -r requirements.txt
	npm install

sprite:
	$(PYTHON) manage.py generate_sprite

migrate:
	$(PYTHON) manage.py migrate

setup: install sprite migrate

run:
	$(PYTHON) manage.py runserver

audit:
	pip-audit -r requirements.txt
