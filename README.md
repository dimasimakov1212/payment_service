# Асинхронный сервис процессинга платежей

## Локальная инфраструктура

Учётные данные и порты задаются через `.env` (см. `.env.example`).

```bash
cp .env.example .env
docker compose up -d postgres rabbitmq
docker compose ps
```

Compose подхватывает `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` из `.env`.
Приложение подключается по `DATABASE_URL` (по умолчанию `localhost:5433`) и `RABBITMQ_URL` (`localhost:5672`).

Проверка готовности:

```bash
docker compose exec postgres pg_isready -U payment -d payment_service
docker compose exec rabbitmq rabbitmq-diagnostics -q ping
```

RabbitMQ UI: [http://localhost:15672](http://localhost:15672) (guest/guest). После `POST /api/v1/payments` сообщение должно появиться в очереди `payments.new`; `payments.new.dlq` остаётся пустой.

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
