.PHONY: help backend frontend up down migrate superuser sandbox-build sandbox-prep

SANDBOX_UID ?= 1000
SANDBOX_GID ?= 1000

help:
	@echo "Cyonima Code Agent Server — commandes"
	@echo "  make up            Démarre db/redis/ollama (docker compose)"
	@echo "  make down          Arrête les services"
	@echo "  make backend       Lance le backend Django (dev)"
	@echo "  make frontend      Lance le frontend React (dev)"
	@echo "  make migrate       Applique les migrations"
	@echo "  make superuser     Crée un superutilisateur"
	@echo "  make sandbox-build Construit l'image du sandbox"
	@echo "  make sandbox-prep  Prépare le volume (ownership) des workspaces"

up:
	docker compose up -d db redis ollama

down:
	docker compose down

backend:
	cd backend && python manage.py runserver

frontend:
	cd frontend && npm run dev

migrate:
	cd backend && python manage.py migrate

worker:
	cd backend && celery -A config worker -l info

migrate-make:
	cd backend && python manage.py makemigrations

superuser:
	cd backend && python manage.py createsuperuser

sandbox-build:
	docker build -t cyonima/sandbox:latest \
		--build-arg UID=$(SANDBOX_UID) --build-arg GID=$(SANDBOX_GID) sandbox/

sandbox-prep:
	mkdir -p sandbox/workspaces
	chown -R $(SANDBOX_UID):$(SANDBOX_GID) sandbox/workspaces
