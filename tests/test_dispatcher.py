import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from caja_clara.dispatcher import OutboxDispatcher
from caja_clara.models import Base, OutboxEvent


@pytest.fixture
def dispatcher_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    yield session_factory
    Base.metadata.drop_all(bind=engine)


@pytest.mark.anyio
async def test_dispatcher_empty_batch(dispatcher_db):
    """Valida que process_batch retorne 0 cuando no hay eventos pendientes."""
    dispatcher = OutboxDispatcher(
        db_factory=dispatcher_db,
        target_url="https://erp.empresa.com/webhooks",
        webhook_secret="test_secret_123",
    )
    count = await dispatcher.process_batch()
    assert count == 0


@pytest.mark.anyio
async def test_dispatcher_successful_delivery(dispatcher_db):
    """Valida el ciclo de vida exitoso de un evento: PENDING -> DELIVERED con HTTP 200."""
    with dispatcher_db() as session:
        event = OutboxEvent(
            event_type="invoice.processed",
            payload='{"invoice_number": "F001-1234", "total": 100.0}',
            status="PENDING",
        )
        session.add(event)
        session.commit()
        event_id = event.id

    def handler(request: httpx.Request) -> httpx.Response:
        assert "X-CajaClara-Signature" in request.headers
        assert "t=" in request.headers["X-CajaClara-Signature"]
        assert request.headers["X-CajaClara-Event-Type"] == "invoice.processed"
        return httpx.Response(200, json={"received": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        dispatcher = OutboxDispatcher(
            db_factory=dispatcher_db,
            http_client=client,
            target_url="https://erp.empresa.com/webhooks",
            webhook_secret="test_secret_123",
        )
        processed_count = await dispatcher.process_batch(limit=10)
        assert processed_count == 1

    with dispatcher_db() as session:
        updated_event = session.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()
        assert updated_event is not None
        assert updated_event.status == "DELIVERED"
        assert updated_event.processed_at is not None
        assert updated_event.error_detail is None


@pytest.mark.anyio
async def test_dispatcher_transient_error_retry(dispatcher_db):
    """Valida que un error HTTP 503 o de red programe un reintento con backoff en next_retry_at."""
    with dispatcher_db() as session:
        event = OutboxEvent(
            event_type="invoice.processed",
            payload='{"invoice_number": "F001-503", "total": 200.0}',
            status="PENDING",
            retry_count=0,
        )
        session.add(event)
        session.commit()
        event_id = event.id

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        dispatcher = OutboxDispatcher(
            db_factory=dispatcher_db,
            http_client=client,
            target_url="https://erp.empresa.com/webhooks",
            webhook_secret="test_secret_123",
        )
        await dispatcher.process_batch(limit=10)

    with dispatcher_db() as session:
        updated_event = session.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()
        assert updated_event.status == "PENDING"
        assert updated_event.retry_count == 1
        assert updated_event.next_retry_at is not None
        next_retry_utc = (
            updated_event.next_retry_at.replace(tzinfo=UTC) if updated_event.next_retry_at.tzinfo is None else updated_event.next_retry_at
        )
        assert next_retry_utc > datetime.now(UTC) - timedelta(seconds=1)
        assert "503" in (updated_event.error_detail or "")


@pytest.mark.anyio
async def test_dispatcher_fatal_client_error_dead_letter(dispatcher_db):
    """Valida que un error HTTP 400/422 pase inmediatamente a DEAD_LETTER sin reintentos."""
    with dispatcher_db() as session:
        event = OutboxEvent(
            event_type="invoice.processed",
            payload='{"invoice_number": "F001-400", "total": -10.0}',
            status="PENDING",
            retry_count=0,
        )
        session.add(event)
        session.commit()
        event_id = event.id

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "Invalid total amount"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        dispatcher = OutboxDispatcher(
            db_factory=dispatcher_db,
            http_client=client,
            target_url="https://erp.empresa.com/webhooks",
            webhook_secret="test_secret_123",
        )
        await dispatcher.process_batch(limit=10)

    with dispatcher_db() as session:
        updated_event = session.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()
        assert updated_event.status == "DEAD_LETTER"
        assert updated_event.retry_count == 0
        assert "400" in (updated_event.error_detail or "")


@pytest.mark.anyio
async def test_dispatcher_network_exception_retry(dispatcher_db):
    """Valida que excepciones de transporte HTTP sean manejadas como error transitorio."""
    with dispatcher_db() as session:
        event = OutboxEvent(
            event_type="invoice.processed",
            payload='{"invoice_number": "F001-NET", "total": 50.0}',
            status="PENDING",
            retry_count=0,
        )
        session.add(event)
        session.commit()
        event_id = event.id

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("Connection timed out to ERP endpoint")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        dispatcher = OutboxDispatcher(
            db_factory=dispatcher_db,
            http_client=client,
            target_url="https://erp.empresa.com/webhooks",
            webhook_secret="test_secret_123",
        )
        await dispatcher.process_batch(limit=10)

    with dispatcher_db() as session:
        updated_event = session.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()
        assert updated_event.status == "PENDING"
        assert updated_event.retry_count == 1
        assert "timed out" in (updated_event.error_detail or "")


@pytest.mark.anyio
async def test_dispatcher_max_retries_dead_letter(dispatcher_db):
    """Valida que al superar el número máximo de reintentos transicione a DEAD_LETTER."""
    with dispatcher_db() as session:
        event = OutboxEvent(
            event_type="invoice.processed",
            payload='{"invoice_number": "F001-MAX", "total": 50.0}',
            status="PENDING",
            retry_count=5,  # Max retries alcanzado
        )
        session.add(event)
        session.commit()
        event_id = event.id

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        dispatcher = OutboxDispatcher(
            db_factory=dispatcher_db,
            http_client=client,
            target_url="https://erp.empresa.com/webhooks",
            webhook_secret="test_secret_123",
            max_retries=5,
        )
        await dispatcher.process_batch(limit=10)

    with dispatcher_db() as session:
        updated_event = session.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()
        assert updated_event.status == "DEAD_LETTER"
        assert "Max reintentos superados" in (updated_event.error_detail or "")


@pytest.mark.anyio
async def test_dispatcher_run_forever_shutdown(dispatcher_db):
    """Valida que run_forever ejecute el ciclo y responda limpiamente al shutdown_event."""
    shutdown_ev = asyncio.Event()

    dispatcher = OutboxDispatcher(
        db_factory=dispatcher_db,
        target_url="https://erp.empresa.com/webhooks",
        webhook_secret="test_secret_123",
    )

    async def trigger_shutdown():
        await asyncio.sleep(0.05)
        shutdown_ev.set()

    task = asyncio.create_task(trigger_shutdown())
    await dispatcher.run_forever(poll_interval=0.01, shutdown_event=shutdown_ev)
    await task
    assert shutdown_ev.is_set()
