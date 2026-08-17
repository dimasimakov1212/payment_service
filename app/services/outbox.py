import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.broker import (
    broker,
    declare_topology,
    payments_exchange,
    payments_new_queue,
)
from app.config import settings
from app.db import async_session_factory
from app.models import OutboxMessage

logger = logging.getLogger(__name__)

OUTBOX_BATCH_SIZE = 50


async def publish_unpublished_batch() -> int:
    """Публикует неопубликованные outbox-события по одному, с SKIP LOCKED."""

    published = 0
    async with async_session_factory() as session:
        for _ in range(OUTBOX_BATCH_SIZE):
            async with session.begin():
                query = (
                    select(OutboxMessage)
                    .where(OutboxMessage.published_at.is_(None))
                    .order_by(OutboxMessage.created_at)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                message = (await session.execute(query)).scalar_one_or_none()
                if message is None:
                    return published

                await broker.publish(
                    message.payload,
                    queue=payments_new_queue,
                    exchange=payments_exchange,
                    message_id=str(message.id),
                    persist=True,
                )
                message.published_at = datetime.now(timezone.utc)
            published += 1
    return published


async def run_outbox_publisher() -> None:
    """Подключается к брокеру и в цикле публикует события из outbox."""

    await broker.start()
    await declare_topology()
    logger.info("Outbox publisher started")
    try:
        while True:
            try:
                await publish_unpublished_batch()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Outbox publish failed")
            await asyncio.sleep(settings.outbox_poll_interval_seconds)
    finally:
        await broker.stop()
        logger.info("Outbox publisher stopped")
