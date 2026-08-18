from __future__ import annotations

import asyncio

from app.enums import PaymentStatus
from app.services import gateway as gateway_module


def test_emulate_gateway_returns_succeeded(monkeypatch):
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(gateway_module.random, "uniform", lambda a, b: 2.5)
    monkeypatch.setattr(gateway_module.random, "random", lambda: 0.1)
    monkeypatch.setattr(gateway_module.asyncio, "sleep", fake_sleep)

    result = asyncio.run(gateway_module.emulate_gateway())

    assert result == PaymentStatus.SUCCEEDED
    assert sleep_calls == [2.5]


def test_emulate_gateway_returns_failed(monkeypatch):
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(gateway_module.random, "uniform", lambda a, b: 4.0)
    monkeypatch.setattr(gateway_module.random, "random", lambda: 0.95)
    monkeypatch.setattr(gateway_module.asyncio, "sleep", fake_sleep)

    result = asyncio.run(gateway_module.emulate_gateway())

    assert result == PaymentStatus.FAILED
    assert sleep_calls == [4.0]

