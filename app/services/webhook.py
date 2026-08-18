import asyncio
import logging

import httpx

from app.schemas.payment import PaymentWebhookPayload

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT_SECONDS = 10.0
WEBHOOK_ATTEMPTS = 3
WEBHOOK_RETRY_DELAYS_SECONDS = (1.0, 2.0)


class WebhookDeliveryError(Exception):
    """Не удалось доставить webhook после всех попыток."""


async def send_webhook(url: str, payload: PaymentWebhookPayload) -> None:
    """Отправляет POST на webhook_url; 3 попытки с паузами 1s и 2s."""

    body = payload.model_dump(mode="json")
    last_error: Exception | None = None

    async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT_SECONDS) as client:
        for attempt in range(1, WEBHOOK_ATTEMPTS + 1):
            try:
                response = await client.post(url, json=body)
                response.raise_for_status()
                logger.info("Webhook delivered to %s for payment %s", url, payload.payment_id)
                return
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "Webhook attempt %s/%s failed for %s: %s",
                    attempt,
                    WEBHOOK_ATTEMPTS,
                    payload.payment_id,
                    exc,
                )
                if attempt < WEBHOOK_ATTEMPTS:
                    await asyncio.sleep(WEBHOOK_RETRY_DELAYS_SECONDS[attempt - 1])

    raise WebhookDeliveryError(
        f"Webhook to {url} failed after {WEBHOOK_ATTEMPTS} attempts",
    ) from last_error
