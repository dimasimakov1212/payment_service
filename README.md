# Асинхронный сервис процессинга платежей

## Локальная БД (Postgres)

Учётные данные и порт задаются через `.env` (см. `.env.example`).

```bash
cp .env.example .env
docker compose up -d postgres
docker compose ps
```

Compose подхватывает `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` из `.env`.
Приложение подключается по `DATABASE_URL` (по умолчанию `localhost:5433`).

Проверка готовности:

```bash
docker compose exec postgres pg_isready -U payment -d payment_service
```

Миграции:

```bash
alembic upgrade head
```

## Запуск приложения

Активация виртуального окружения:

```bash
source .venv/bin/activate
```

Запуск:

```bash
uvicorn app.api.main:app --reload --port 8000
```

## API

OpenAPI: `http://localhost:8000/docs`

Создание платежа:

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "X-API-Key: dev-api-key" \
  -H "Idempotency-Key: test-1" \
  -H "Content-Type: application/json" \
  -d '{"amount":"100.50","currency":"RUB","description":"test payment","metadata":{"order_id":"A-1"},"webhook_url":"https://example.com/hook"}'
```

Получение платежа:

```bash
curl -X GET http://localhost:8000/api/v1/payments/<payment_id> \
  -H "X-API-Key: dev-api-key"
```
