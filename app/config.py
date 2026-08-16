from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://payment:payment@localhost:5432/payment_service"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    api_key: str = "dev-api-key"
    outbox_poll_interval_seconds: float = 1.0


settings = Settings()
