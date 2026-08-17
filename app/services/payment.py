import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OutboxMessage, Payment
from app.schemas.payment import PaymentCreateRequest


async def get_payment_by_id(session: AsyncSession, payment_id: uuid.UUID) -> Payment | None:
    """Возвращает платёж по первичному ключу или None."""

    return await session.get(Payment, payment_id)


async def get_payment_by_idempotency_key(
    session: AsyncSession,
    idempotency_key: str,
) -> Payment | None:
    """Ищет платёж по Idempotency-Key для защиты от дублей."""

    query = select(Payment).where(Payment.idempotency_key == idempotency_key)
    result = await session.execute(query)

    return result.scalar_one_or_none()


async def create_payment(
    session: AsyncSession,
    payload: PaymentCreateRequest,
    idempotency_key: str,
) -> Payment:
    """Создаёт платёж и outbox-событие; при повторе ключа возвращает существующий."""

    existing = await get_payment_by_idempotency_key(session, idempotency_key)
    if existing is not None:
        return existing

    try:
        payment = Payment(
            amount=payload.amount,
            currency=payload.currency,
            description=payload.description,
            metadata_=payload.metadata,
            idempotency_key=idempotency_key,
            webhook_url=str(payload.webhook_url),
        )
        session.add(payment)
        await session.flush()

        outbox_message = OutboxMessage(
            aggregate_id=payment.id,
            event_type="payments.new",
            payload={"payment_id": str(payment.id)},
        )
        session.add(outbox_message)
        await session.commit()
        await session.refresh(payment)
        return payment
        
    except IntegrityError:
        await session.rollback()
        existing = await get_payment_by_idempotency_key(session, idempotency_key)
        if existing is not None:
            return existing
        raise
