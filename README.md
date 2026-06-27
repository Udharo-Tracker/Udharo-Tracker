# Udharo Tracker — उधारो ट्र्याकर

A REST API for small shop owners in Nepal to manage credit debt. **Udharo** (उधारो) means credit given on trust — goods handed over now, payment collected later. This system helps shop owners track what customers owe, record payments, and stay on top of outstanding balances.

---

## Features

- Register customers and record items sold on credit
- Accept and log payments against a customer's balance
- View a full statement per customer
- Dashboard and ledger summary with outstanding balances
- Monthly income and activity reports
- Automated daily credit scoring per customer (green / yellow / red risk)
- Automated reminder logging for overdue balances
- JWT-based authentication with token refresh and logout
- Interactive API docs (Swagger UI and ReDoc)

---

## Tech Stack

- **Django 6.0+** with Django REST Framework
- **PostgreSQL** — primary database
- **Redis** — caching and Celery message broker
- **Celery + Celery Beat** — async and scheduled tasks
- **SimpleJWT** — authentication
- **drf-spectacular** — OpenAPI documentation
- **uv** — Python package management
- **Docker Compose** — containerized deployment

---

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL
- Redis
- [uv](https://github.com/astral-sh/uv)

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure environment

```bash
cp backend/.env.example backend/.env
```

Fill in `backend/.env` with your database credentials, secret key, and Redis URL.

### 3. Run migrations and start the server

```bash
cd backend
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### 4. Start Celery workers (separate terminals)

```bash
# Task worker
celery -A config worker -l info

# Beat scheduler (for daily tasks)
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

---

## Docker

```bash
cd backend
cp .env.example .env.prod   # fill in production values

docker compose up --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

---

## API Documentation

Once the server is running, visit:

- Swagger UI: `http://localhost:8000/schema/swagger/`
- ReDoc: `http://localhost:8000/schema/redoc/`

All endpoints require JWT authentication. Pass the token as:

```
Authorization: Bearer <access_token>
```

---

## Running Tests

```bash
cd backend
python manage.py test
```

---

## License

MIT
