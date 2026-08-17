from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

from app.config import settings

PAYMENTS_EXCHANGE_NAME = "payments"
PAYMENTS_NEW_QUEUE_NAME = "payments.new"
PAYMENTS_DLX_NAME = "payments.dlx"
PAYMENTS_DLQ_NAME = "payments.new.dlq"

broker = RabbitBroker(settings.rabbitmq_url)

payments_exchange = RabbitExchange(
    PAYMENTS_EXCHANGE_NAME,
    type=ExchangeType.DIRECT,
    durable=True,
)

dlx_exchange = RabbitExchange(
    PAYMENTS_DLX_NAME,
    type=ExchangeType.DIRECT,
    durable=True,
)

payments_new_queue = RabbitQueue(
    PAYMENTS_NEW_QUEUE_NAME,
    durable=True,
    routing_key=PAYMENTS_NEW_QUEUE_NAME,
    arguments={
        "x-dead-letter-exchange": PAYMENTS_DLX_NAME,
        "x-dead-letter-routing-key": PAYMENTS_DLQ_NAME,
    },
)

payments_dlq = RabbitQueue(
    PAYMENTS_DLQ_NAME,
    durable=True,
    routing_key=PAYMENTS_DLQ_NAME,
)


async def declare_topology() -> None:
    """Объявляет exchange, очереди и binding; без bind publish теряет сообщения."""

    declared_payments_exchange = await broker.declare_exchange(payments_exchange)
    declared_dlx = await broker.declare_exchange(dlx_exchange)

    declared_new_queue = await broker.declare_queue(payments_new_queue)
    declared_dlq_queue = await broker.declare_queue(payments_dlq)

    await declared_new_queue.bind(
        declared_payments_exchange,
        routing_key=payments_new_queue.routing,
    )
    await declared_dlq_queue.bind(
        declared_dlx,
        routing_key=payments_dlq.routing,
    )
