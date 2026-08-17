import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_factory
from app.enums import PaymentStatus
from app.models import OutboxMessage, Payment
from app.schemas.payment import PaymentCreateRequest
from app.services.gateway import emulate_gateway


class PaymentNotFoundError(LookupError):
    """Платёж с указанным id не найден."""


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


async def process_new_payment(payment_id: uuid.UUID) -> Payment:
    """Обрабатывает платёж из очереди: эмуляция шлюза только для pending."""

    async with async_session_factory() as session:
        async with session.begin():
            payment = await session.get(Payment, payment_id, with_for_update=True)
            if payment is None:
                raise PaymentNotFoundError(f"Payment {payment_id} not found")
            if payment.status != PaymentStatus.PENDING:
                return payment

            payment.status = await emulate_gateway()
            payment.processed_at = datetime.now(timezone.utc)
            return payment
