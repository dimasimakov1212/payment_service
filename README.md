# Асинхронный сервис процессинга платежей

Сервис принимает запросы на оплату, сохраняет платёж в БД и публикует событие в очередь через Outbox pattern. Отдельный consumer эмулирует внешний шлюз, обновляет финальный статус платежа и отправляет webhook клиенту.

## Основные возможности

- Идемпотентное создание платежа через `Idempotency-Key`
- Гарантированная публикация событий через Outbox (`payments.new`)
- Асинхронная обработка через RabbitMQ + FastStream
- Retry webhook до 3 попыток с задержками `1s` и `2s`
- Dead Letter Queue для недоставленных webhook (`payments.new.dlq`)
- Авторизация API через `X-API-Key`

## Поток обработки

1. `POST /api/v1/payments` создаёт платёж со статусом `pending` и outbox-событие в одной транзакции.
2. Outbox publisher публикует событие в очередь `payments.new`.
3. Consumer обрабатывает платёж (успех/ошибка), обновляет `status` и `processed_at`.
4. Consumer отправляет webhook с итоговым результатом.

## Запуск (Docker, рекомендуется)

Поднимает postgres, rabbitmq, migrate (схема БД), api и consumer одной командой:

```bash
cp .env.example .env   # опционально: POSTGRES_PORT, API_KEY
docker compose up --build
```

Проверка:

```bash
curl http://localhost:8000/health
docker compose ps
# postgres, rabbitmq, api, consumer — running/healthy
# migrate — Exited (0)
```

Сервис `migrate` один раз выполняет `alembic upgrade head` и завершается. API слушает `:8000`, consumer обрабатывает очередь `payments.new`.

RabbitMQ UI: [http://localhost:15672](http://localhost:15672) (guest/guest).

Остановка:

```bash
docker compose down
```

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

После `POST /api/v1/payments` через 2–5 секунд `GET /api/v1/payments/{id}` должен вернуть `succeeded` или `failed` и заполненный `processed_at`. В RabbitMQ UI у `payments.new` Ready падает до 0.

Webhook:

- Успех: укажите URL, который принимает POST, например `https://httpbin.org/post` или [webhook.site](https://webhook.site).
- DLQ: заведомо мёртвый URL (`http://127.0.0.1:1` или `https://httpbin.org/status/500`). После трёх попыток (паузы 1s и 2s) сообщение окажется в `payments.new.dlq`; статус в БД уже финальный.

## Локальная разработка (без контейнеров api/consumer)

Только инфраструктура в Docker, приложение на хосте:

```bash
cp .env.example .env
docker compose up -d postgres rabbitmq
docker compose ps
```

`DATABASE_URL` и `RABBITMQ_URL` в `.env` — с `localhost` (см. `.env.example`).

Проверка готовности:

```bash
docker compose exec postgres pg_isready -U payment -d payment_service
docker compose exec rabbitmq rabbitmq-diagnostics -q ping
```

Миграции:

```bash
source .venv/bin/activate
alembic upgrade head
```

API (outbox-publisher внутри процесса):

```bash
uvicorn app.api.main:app --reload --port 8000
```

Consumer (эмуляция шлюза, статус, webhook):

```bash
faststream run app.consumer.main:app
```
