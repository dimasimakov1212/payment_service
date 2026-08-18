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

RabbitMQ UI: [http://localhost:15672](http://localhost:15672) (guest/guest). После `POST /api/v1/payments` сообщение появляется в `payments.new`; consumer забирает его, обновляет статус и шлёт webhook. Если webhook не доставить за 3 попытки, сообщение уходит в `payments.new.dlq`.

Миграции:

```bash
alembic upgrade head
```

## Запуск приложения

Активация виртуального окружения:

```bash
source .venv/bin/activate
```

API (outbox-publisher внутри процесса):

```bash
uvicorn app.api.main:app --reload --port 8000
```

Consumer (эмуляция шлюза, статус, webhook):

```bash
faststream run app.consumer.main:app
```

После `POST /api/v1/payments` через 2–5 секунд `GET /api/v1/payments/{id}` должен вернуть `succeeded` или `failed` и заполненный `processed_at`. В RabbitMQ UI у `payments.new` Ready падает до 0.

Webhook:

- Успех: укажите URL, который принимает POST, например `https://httpbin.org/post` или [webhook.site](https://webhook.site).
- DLQ: заведомо мёртвый URL (`http://127.0.0.1:1` или `https://httpbin.org/status/500`). После трёх попыток (паузы 1s и 2s) сообщение окажется в `payments.new.dlq`; статус в БД уже финальный.

## API

OpenAPI: `http://localhost:8000/docs`

Создание платежа:

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "X-API-Key: dev-api-key" \
  -H "Idempotency-Key: test-1" \
  -H "Content-Type: application/json" \
  -d '{"amount":"100.50","currency":"RUB","description":"test payment","metadata":{"order_id":"A-1"},"webhook_url":"https://httpbin.org/post"}'
```

Получение платежа:

```bash
curl -X GET http://localhost:8000/api/v1/payments/<payment_id> \
  -H "X-API-Key: dev-api-key"
```
