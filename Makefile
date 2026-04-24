PYTHON ?= .venv/bin/python

.PHONY: help install-backend install-frontend install

help:
	@echo "Targets:"
	@echo "  install-backend  - pip install backend/requirements.txt"
	@echo "  install-frontend - npm install in frontend/"
	@echo "  install          - both"

install-backend:
	$(PYTHON) -m pip install -r backend/requirements.txt

install-frontend:
	cd frontend && npm install

install: install-backend install-frontend
