import uuid

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_api_key
from app.schemas import PaymentCreateRequest, PaymentCreateResponse, PaymentResponse
from app.services.payment import create_payment, get_payment_by_id

app = FastAPI(
    title="Payment Processing Service",
    description="Асинхронный сервис процессинга платежей.",
    version="0.1.0",
)

payments_router = APIRouter(
    prefix="/api/v1/payments",
    tags=["payments"],
    dependencies=[Depends(verify_api_key)],
)


@app.get("/health", summary="Проверка доступности")
async def health() -> dict[str, str]:
    """Проверка доступности сервиса без аутентификации."""
    return {"status": "ok"}


@payments_router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PaymentCreateResponse,
    summary="Создать платёж",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Неверный или отсутствующий X-API-Key"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Невалидное тело запроса или нет Idempotency-Key",
        },
    },
)
async def create_payment_endpoint(
    payload: PaymentCreateRequest,
    session: AsyncSession = Depends(get_db),
    idempotency_key: str = Header(
        alias="Idempotency-Key",
        min_length=1,
        description="Уникальный ключ запроса; повтор вернёт тот же платёж",
    ),
) -> PaymentCreateResponse:
    """Создаёт платёж и outbox-событие payments.new в одной транзакции."""

    payment = await create_payment(
        session=session,
        payload=payload,
        idempotency_key=idempotency_key,
    )
    return PaymentCreateResponse(
        payment_id=payment.id,
        status=payment.status,
        created_at=payment.created_at,
    )


@payments_router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Получить платёж",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Неверный или отсутствующий X-API-Key"},
        status.HTTP_404_NOT_FOUND: {"description": "Платёж не найден"},
    },
)
async def get_payment_endpoint(
    payment_id: uuid.UUID = Path(description="Идентификатор платежа"),
    session: AsyncSession = Depends(get_db),
) -> PaymentResponse:
    """Возвращает детальную информацию о платеже по id."""

    payment = await get_payment_by_id(session, payment_id)
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    return PaymentResponse.model_validate(payment)


app.include_router(payments_router)
