.PHONY: help backend frontend up down migrate superuser sandbox-build

help:
	@echo "Cyonima Code Agent Server — commandes"
	@echo "  make up            Démarre db/redis/ollama (docker compose)"
	@echo "  make down          Arrête les services"
	@echo "  make backend       Lance le backend Django (dev)"
	@echo "  make frontend      Lance le frontend React (dev)"
	@echo "  make migrate       Applique les migrations"
	@echo "  make superuser     Crée un superutilisateur"
	@echo "  make sandbox-build Construit l'image du sandbox"

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
	docker build -t cyonima/sandbox:latest sandbox/
