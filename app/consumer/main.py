import logging

from faststream import FastStream
from faststream.exceptions import RejectMessage
from faststream.rabbit import Channel

from app.broker import (
    broker,
    declare_topology,
    payments_exchange,
    payments_new_queue,
)
from app.schemas.payment import PaymentEvent, PaymentWebhookPayload
from app.services.payment import PaymentNotFoundError, process_new_payment
from app.services.webhook import WebhookDeliveryError, send_webhook

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
    """Обрабатывает payments.new: шлюз, статус, webhook; при сбое — DLQ."""

    try:
        payment = await process_new_payment(payload.payment_id)
    except PaymentNotFoundError:
        logger.exception("Payment %s not found", payload.payment_id)
        raise RejectMessage() from None

    logger.info("Payment %s status=%s", payment.id, payment.status)

    webhook_payload = PaymentWebhookPayload(
        payment_id=payment.id,
        status=payment.status,
        amount=payment.amount,
        currency=payment.currency,
        processed_at=payment.processed_at,
    )
    try:
        await send_webhook(payment.webhook_url, webhook_payload)
    except WebhookDeliveryError:
        logger.exception("Webhook failed for payment %s, sending to DLQ", payment.id)
        raise RejectMessage() from None
