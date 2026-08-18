import json
import threading
import time
from collections.abc import Iterator
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from queue import Queue
from socketserver import ThreadingMixIn
from typing import Any
from uuid import uuid4

import httpx
import pytest


BASE_URL = "http://localhost:8000"
RABBITMQ_API_URL = "http://localhost:15672/api"

# Считаем, что docker compose уже поднят и использует тот же API key (см. .env)
API_KEY = "dev-api-key"


def _get_env_api_key() -> str:
    # Минимальная защита от ситуации, когда переменная окружения не прокинута в тестовый процесс
    import os

    return os.getenv("API_KEY", API_KEY)


def _random_idempotency_key() -> str:
    return str(uuid4())


def _build_payment_payload(
    *,
    amount: str,
    currency: str,
    description: str,
    metadata: dict[str, Any],
    webhook_url: str,
) -> dict[str, Any]:
    """Строит payload для создания платежа"""
    
    return {
        "amount": amount,
        "currency": currency,
        "description": description,
        "metadata": metadata,
        "webhook_url": webhook_url,
    }


def _headers() -> dict[str, str]:
    """Строит headers для запроса"""
    
    return {"X-API-Key": _get_env_api_key()}


def _payment_json(api_response: httpx.Response) -> dict[str, Any]:
    """Парсит JSON из ответа API"""
    
    api_response.raise_for_status()
    return api_response.json()


def wait_until(
    *,
    condition: Callable[[], bool],
    timeout_seconds: float,
    poll_interval_seconds: float = 0.5,
    on_timeout_message: str,
) -> None:
    """Ожидает выполнения условия"""
    
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(poll_interval_seconds)
    raise AssertionError(on_timeout_message)


def get_queue_messages(queue_name: str) -> int:
    """Возвращает количество сообщений в очереди RabbitMQ через management API."""

    url = f"{RABBITMQ_API_URL}/queues/%2F/{queue_name}"
    auth = httpx.BasicAuth("guest", "guest")
    with httpx.Client(timeout=5.0) as client:
        resp = client.get(url, auth=auth)
        resp.raise_for_status()
        data = resp.json()
    return int(data["messages"])


@pytest.fixture()
def api_client() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        yield client


def create_payment(
    *,
    client: httpx.Client,
    idempotency_key: str,
    amount: str,
    currency: str,
    description: str,
    metadata: dict[str, Any],
    webhook_url: str,
) -> dict[str, Any]:
    """Создает платеж через API"""

    payload = _build_payment_payload(
        amount=amount,
        currency=currency,
        description=description,
        metadata=metadata,
        webhook_url=webhook_url,
    )

    headers = _headers()
    headers["Idempotency-Key"] = idempotency_key
    resp = client.post("/api/v1/payments", json=payload, headers=headers)
    return _payment_json(resp)


def get_payment(
    *,
    client: httpx.Client,
    payment_id: str,
) -> dict[str, Any]:
    """Получает платеж через API"""

    resp = client.get(f"/api/v1/payments/{payment_id}", headers=_headers())
    return _payment_json(resp)


def wait_for_payment_finished(
    *,
    client: httpx.Client,
    payment_id: str,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    result: dict[str, Any] | None = None
    """Ожидает завершения платежа через API"""

    def _done() -> bool:
        nonlocal result
        data = get_payment(client=client, payment_id=payment_id)
        result = data
        return data["status"] != "pending"

    wait_until(
        condition=_done,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=0.5,
        on_timeout_message=f"Payment {payment_id} did not finish in time",
    )
    assert result is not None
    return result


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


@pytest.fixture()
def mock_webhook() -> Iterator[str]:
    """
    Простейший локальный webhook-server для проверки success/idempotency без DLQ.

    Consumer делает HTTP POST на webhook_url. Мы отвечаем 200 OK всегда.
    """

    received: "Queue[dict[str, Any]]" = Queue()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                payload = {"raw": raw.decode("utf-8", errors="replace")}
            received.put(payload)

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: N802
            # Отключаем лишний шум в консоли тестов
            return

    server = _ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    webhook_url = f"http://127.0.0.1:{port}/webhook"
    try:
        yield webhook_url
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture()
def webhook_fail_url() -> str:
    # Connection refused почти сразу -> быстрые 3 попытки retry (1s и 2s между ними)
    return "http://127.0.0.1:1/does-not-exist"


@pytest.fixture()
def idempotency_key() -> str:
    return _random_idempotency_key()


@pytest.fixture()
def dlq_queue_name() -> str:
    return "payments.new.dlq"

