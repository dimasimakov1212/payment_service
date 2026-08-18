from __future__ import annotations

from decimal import Decimal


def test_payment_success_flow(
    api_client,
    mock_webhook: str,
    idempotency_key: str,
):
    """Тест успешного потока платежа"""

    from tests.conftest import create_payment, wait_for_payment_finished

    description = "success test"
    metadata = {"order_id": "A-1"}

    created = create_payment(
        client=api_client,
        idempotency_key=idempotency_key,
        amount="1000.00",
        currency="RUB",
        description=description,
        metadata=metadata,
        webhook_url=mock_webhook,
    )

    payment_id = str(created["payment_id"])
    assert created["status"] == "pending"

    payment = wait_for_payment_finished(
        client=api_client,
        payment_id=payment_id,
        timeout_seconds=20.0,
    )

    assert payment["status"] in {"succeeded", "failed"}
    assert payment["processed_at"] is not None
    assert Decimal(str(payment["amount"])) == Decimal("1000.00")
    assert payment["currency"] == "RUB"
    assert payment["description"] == description
    assert payment["metadata"] is not None
    assert payment["metadata"]["order_id"] == metadata["order_id"]


def test_payment_idempotency(
    api_client,
    mock_webhook: str,
):
    """Тест идемпотентности платежа"""
    
    import uuid
    from tests.conftest import create_payment, get_payment, wait_for_payment_finished

    idempotency_key = str(uuid.uuid4())
    description = "idempotency test"
    metadata = {"order_id": "B-1"}

    created_1 = create_payment(
        client=api_client,
        idempotency_key=idempotency_key,
        amount="42.00",
        currency="RUB",
        description=description,
        metadata=metadata,
        webhook_url=mock_webhook,
    )
    payment_id_1 = str(created_1["payment_id"])

    assert created_1["status"] == "pending"

    created_2 = create_payment(
        client=api_client,
        idempotency_key=idempotency_key,
        amount="42.00",
        currency="RUB",
        description=description,
        metadata=metadata,
        webhook_url=mock_webhook,
    )
    payment_id_2 = str(created_2["payment_id"])
    assert created_2["status"] == created_1["status"]
    assert payment_id_2 == payment_id_1

    payment = wait_for_payment_finished(
        client=api_client,
        payment_id=payment_id_1,
        timeout_seconds=20.0,
    )
    assert payment["processed_at"] is not None

    current = get_payment(client=api_client, payment_id=payment_id_2)
    assert current["id"] == payment_id_2


def test_failed_webhook_goes_to_dlq(
    api_client,
    webhook_fail_url: str,
    dlq_queue_name: str,
):
    """Тест ошибки webhook переводит платеж в DLQ"""
    
    from tests.conftest import create_payment, get_queue_messages, wait_for_payment_finished, wait_until

    before = get_queue_messages(dlq_queue_name)

    created = create_payment(
        client=api_client,
        idempotency_key="dlq-test-" + dlq_queue_name + "-1",
        amount="10.00",
        currency="RUB",
        description="dlq test",
        metadata={"order_id": "DLQ-1"},
        webhook_url=webhook_fail_url,
    )
    payment_id = str(created["payment_id"])

    # Платёж должен перейти в финальный статус (succeeded/failed) независимо от webhook delivery
    wait_for_payment_finished(
        client=api_client,
        payment_id=payment_id,
        timeout_seconds=20.0,
    )

    # Сообщение должно уйти в DLQ после 3 попыток webhook (1s и 2s между попытками).
    # Проверяем рост счетчика сообщений в очереди.
    def dlq_increased() -> bool:
        after = get_queue_messages(dlq_queue_name)
        return after >= before + 1

    wait_until(
        condition=dlq_increased,
        timeout_seconds=60.0,
        poll_interval_seconds=1.0,
        on_timeout_message="DLQ did not receive the message in time",
    )

