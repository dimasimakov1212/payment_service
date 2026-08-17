import asyncio
import random

from app.enums import PaymentStatus

GATEWAY_MIN_DELAY_SECONDS = 2.0
GATEWAY_MAX_DELAY_SECONDS = 5.0
GATEWAY_SUCCESS_RATE = 0.9


async def emulate_gateway() -> PaymentStatus:
    """Эмулирует внешний платёжный шлюз: задержка 2–5 сек, 90% успеха."""

    await asyncio.sleep(
        random.uniform(GATEWAY_MIN_DELAY_SECONDS, GATEWAY_MAX_DELAY_SECONDS),
    )
    if random.random() < GATEWAY_SUCCESS_RATE:
        return PaymentStatus.SUCCEEDED
    return PaymentStatus.FAILED
