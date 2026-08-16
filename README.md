# Асинхронный сервис процессинга платежей

## Локальная БД (Postgres)

```bash
cp .env.example .env
docker compose up -d postgres
docker compose ps
```

DSN совпадает с `DATABASE_URL` в `.env.example`:

`postgresql+asyncpg://payment:payment@localhost:5433/payment_service`

Проверка готовности:

```bash
docker compose exec postgres pg_isready -U payment -d payment_service
```
