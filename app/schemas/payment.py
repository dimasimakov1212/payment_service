import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.enums import Currency, PaymentStatus


class PaymentCreateRequest(BaseModel):
    """Тело запроса на создание платежа."""

    amount: Decimal = Field(gt=0, description="Сумма платежа")
    currency: Currency = Field(description="Валюта: RUB, USD или EUR")
    description: str = Field(description="Описание платежа")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные данные платежа",
    )
    webhook_url: HttpUrl = Field(description="URL для уведомления о результате")


class PaymentEvent(BaseModel):
    """Событие payments.new из очереди."""

    payment_id: uuid.UUID = Field(description="Идентификатор платежа")


class PaymentWebhookPayload(BaseModel):
    """Тело POST-уведомления на webhook_url."""

    payment_id: uuid.UUID = Field(description="Идентификатор платежа")
    status: PaymentStatus = Field(description="Итоговый статус: succeeded или failed")
    amount: Decimal = Field(description="Сумма платежа")
    currency: Currency = Field(description="Валюта платежа")
    processed_at: datetime | None = Field(description="Дата и время обработки")


class PaymentCreateResponse(BaseModel):
    """Ответ POST /api/v1/payments (202 Accepted)."""

    payment_id: uuid.UUID = Field(description="Идентификатор платежа")
    status: PaymentStatus = Field(description="Текущий статус платежа")
    created_at: datetime = Field(description="Дата и время создания")


class PaymentResponse(BaseModel):
    """Полная карточка платежа для GET /api/v1/payments/{payment_id}."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID = Field(description="Идентификатор платежа")
    amount: Decimal = Field(description="Сумма платежа")
    currency: Currency = Field(description="Валюта: RUB, USD или EUR")
    description: str = Field(description="Описание платежа")
    metadata: dict[str, Any] | None = Field(
        default=None,
        validation_alias="metadata_",
        serialization_alias="metadata",
        description="Дополнительные данные платежа",
    )
    status: PaymentStatus = Field(description="Статус: pending, succeeded или failed")
    webhook_url: str = Field(description="URL для уведомления о результате")
    created_at: datetime = Field(description="Дата и время создания")
    processed_at: datetime | None = Field(
        default=None,
        description="Дата и время обработки; null, пока платёж в pending",
    )
