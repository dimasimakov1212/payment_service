import logging

from faststream import FastStream
from faststream.rabbit import Channel

from app.broker import (
    broker,
    declare_topology,
    payments_exchange,
    payments_new_queue,
)
from app.schemas.payment import PaymentEvent
from app.services.payment import PaymentNotFoundError, process_new_payment

logger = logging.getLogger(__name__)

app = FastStream(broker)


@app.after_startup
async def on_startup() -> None:
    """Гарантирует топологию (включая DLQ), если consumer стартовал раньше API."""

    await declare_topology()
    logger.info("Payment consumer started")


@broker.subscriber(
    payments_new_queue,
    payments_exchange,
    channel=Channel(prefetch_count=1),
)


async def handle_payment(payload: PaymentEvent) -> None:
    """Обрабатывает событие payments.new: эмуляция шлюза и обновление статуса."""

    try:
        payment = await process_new_payment(payload.payment_id)
    except PaymentNotFoundError:
        logger.exception("Payment %s not found", payload.payment_id)
        raise

    logger.info("Payment %s status=%s", payment.id, payment.status)
