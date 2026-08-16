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
