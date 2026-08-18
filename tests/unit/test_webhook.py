from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest

from app.enums import Currency, PaymentStatus
from app.schemas.payment import PaymentWebhookPayload
from app.services import webhook as webhook_module


class DummyResponse:
    def __init__(self, *, should_raise: bool = False, error: Exception | None = None) -> None:
        self.should_raise = should_raise
        self.error = error

    def raise_for_status(self) -> None:
        if self.should_raise:
            assert self.error is not None
            raise self.error


class FakeAsyncClient:
    responses: list[object] = []
    calls: list[tuple[str, dict]] = []

    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, json: dict) -> DummyResponse:
        self.calls.append((url, json))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    @classmethod
    def reset(cls, responses: list[object]) -> None:
        cls.responses = list(responses)
        cls.calls = []


def build_payload() -> PaymentWebhookPayload:
    return PaymentWebhookPayload(
        payment_id=uuid.uuid4(),
        status=PaymentStatus.SUCCEEDED,
        amount=Decimal("1000.00"),
        currency=Currency.RUB,
        processed_at=datetime.now(timezone.utc),
    )


def test_send_webhook_succeeds_on_first_attempt(monkeypatch):
    payload = build_payload()
    FakeAsyncClient.reset([DummyResponse()])
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(webhook_module.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(webhook_module.asyncio, "sleep", fake_sleep)

    asyncio.run(webhook_module.send_webhook("https://example.test/webhook", payload))

    assert len(FakeAsyncClient.calls) == 1
    assert FakeAsyncClient.calls[0][0] == "https://example.test/webhook"
    sent_body = FakeAsyncClient.calls[0][1]
    assert sent_body["payment_id"] == str(payload.payment_id)
    assert sent_body["status"] == payload.status.value
    assert sent_body["amount"] == "1000.00"
    assert sent_body["currency"] == "RUB"
    assert sleep_calls == []


def test_send_webhook_retries_and_then_succeeds(monkeypatch):
    payload = build_payload()
    error = httpx.ConnectError("temporary network error")
    FakeAsyncClient.reset([error, error, DummyResponse()])
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(webhook_module.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(webhook_module.asyncio, "sleep", fake_sleep)

    asyncio.run(webhook_module.send_webhook("https://example.test/webhook", payload))

    assert len(FakeAsyncClient.calls) == 3
    assert sleep_calls == [1.0, 2.0]


def test_send_webhook_raises_after_all_attempts(monkeypatch):
    payload = build_payload()
    error = httpx.ConnectError("all attempts failed")
    FakeAsyncClient.reset([error, error, error])
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(webhook_module.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(webhook_module.asyncio, "sleep", fake_sleep)

    with pytest.raises(webhook_module.WebhookDeliveryError, match="failed after 3 attempts"):
        asyncio.run(webhook_module.send_webhook("https://example.test/webhook", payload))

    assert len(FakeAsyncClient.calls) == 3
    assert sleep_calls == [1.0, 2.0]

