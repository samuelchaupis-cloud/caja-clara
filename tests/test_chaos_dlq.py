from datetime import UTC, datetime, timedelta

import httpx
import pytest

from caja_clara.cli_admin import (
    list_outbox_events,
    replay_all_dead_letters,
    replay_outbox_event,
)
from caja_clara.cli_admin import (
    main as cli_main,
)
from caja_clara.dispatcher import OutboxDispatcher
from caja_clara.models import OutboxEvent
from caja_clara.notifications import (
    format_telegram_alert,
    format_whatsapp_alert,
    send_multichannel_notification,
)


@pytest.mark.anyio
async def test_dispatcher_chaos_429_retry_after(db_session):
    """Valida que ante HTTP 429 con Retry-After, el reintento se programe respetando la cabecera."""
    ev = OutboxEvent(
        event_type="invoice.processed",
        payload='{"doc": "F001-1"}',
        status="PENDING",
        retry_count=0,
    )
    db_session.add(ev)
    db_session.commit()
    ev_id = ev.id

    def rate_limit_mock(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "30"}, text="Rate limit exceeded")

    transport = httpx.MockTransport(rate_limit_mock)
    async with httpx.AsyncClient(transport=transport) as client:
        dispatcher = OutboxDispatcher(db_factory=lambda: db_session, http_client=client, base_delay=1.0)
        await dispatcher.process_batch()

    updated = db_session.query(OutboxEvent).filter(OutboxEvent.id == ev_id).first()
    assert updated is not None
    assert updated.status == "PENDING"
    assert updated.retry_count == 1
    # next_retry_at debe ser mayor a 25 segundos en el futuro (respetando los 30s de Retry-After)
    expected_min = datetime.now(UTC) + timedelta(seconds=25)
    assert updated.next_retry_at.replace(tzinfo=UTC) >= expected_min


@pytest.mark.anyio
async def test_dispatcher_chaos_401_fatal_dead_letter(db_session):
    """Valida que un error HTTP 401 transicione de inmediato a DEAD_LETTER."""
    ev = OutboxEvent(
        event_type="invoice.processed",
        payload='{"doc": "F001-2"}',
        status="PENDING",
        retry_count=0,
    )
    db_session.add(ev)
    db_session.commit()
    ev_id = ev.id

    def auth_error_mock(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "Token expired"})

    transport = httpx.MockTransport(auth_error_mock)
    async with httpx.AsyncClient(transport=transport) as client:
        dispatcher = OutboxDispatcher(db_factory=lambda: db_session, http_client=client)
        await dispatcher.process_batch()

    updated = db_session.query(OutboxEvent).filter(OutboxEvent.id == ev_id).first()
    assert updated is not None
    assert updated.status == "DEAD_LETTER"
    assert "HTTP 401" in (updated.error_detail or "")


@pytest.mark.anyio
async def test_dispatcher_chaos_max_retries_dead_letter(db_session):
    """Valida que al superar max_retries=5, el evento transicione a DEAD_LETTER."""
    ev = OutboxEvent(
        event_type="invoice.processed",
        payload='{"doc": "F001-3"}',
        status="PENDING",
        retry_count=5,  # Último reintento
    )
    db_session.add(ev)
    db_session.commit()
    ev_id = ev.id

    def server_500_mock(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(server_500_mock)
    async with httpx.AsyncClient(transport=transport) as client:
        dispatcher = OutboxDispatcher(db_factory=lambda: db_session, http_client=client, max_retries=5)
        await dispatcher.process_batch()

    updated = db_session.query(OutboxEvent).filter(OutboxEvent.id == ev_id).first()
    assert updated is not None
    assert updated.status == "DEAD_LETTER"
    assert "Max reintentos superados" in (updated.error_detail or "")


def test_dispatcher_recover_stuck_events(db_session):
    """Valida la recuperación de eventos huérfanos congelados en PROCESSING."""
    old_time = datetime.now(UTC) - timedelta(minutes=10)
    ev = OutboxEvent(
        event_type="invoice.processed",
        payload='{"doc": "F001-4"}',
        status="PROCESSING",
        created_at=old_time,
        next_retry_at=old_time,
    )
    db_session.add(ev)
    db_session.commit()
    ev_id = ev.id

    dispatcher = OutboxDispatcher(db_factory=lambda: db_session)
    recovered = dispatcher.recover_stuck_events(timeout_minutes=5)
    assert recovered == 1

    updated = db_session.query(OutboxEvent).filter(OutboxEvent.id == ev_id).first()
    assert updated is not None
    assert updated.status == "PENDING"


def test_cli_admin_list_and_replay(db_session):
    """Valida las operaciones del CLI administrativo list_outbox_events y replay_outbox_event."""
    # 1. Crear evento en DEAD_LETTER
    ev = OutboxEvent(
        event_type="fiscal.alert.cdr_rejected",
        payload='{"invoice": "F001-99"}',
        status="DEAD_LETTER",
        error_detail="Timeout 504",
        retry_count=5,
    )
    db_session.add(ev)
    db_session.commit()
    ev_id = ev.id

    # 2. Listar eventos
    events = list_outbox_events(db_factory=lambda: db_session, status="DEAD_LETTER")
    assert len(events) >= 1
    assert any(e["id"] == ev_id for e in events)

    # 3. Reprocesar individual
    success = replay_outbox_event(db_factory=lambda: db_session, event_id=ev_id)
    assert success is True

    # 4. Verificar cambio a PENDING
    replayed = db_session.query(OutboxEvent).filter(OutboxEvent.id == ev_id).first()
    assert replayed is not None
    assert replayed.status == "PENDING"
    assert replayed.retry_count == 0
    assert replayed.error_detail is None

    # 5. Reprocesar no existente o no DEAD_LETTER debe devolver False
    assert replay_outbox_event(db_factory=lambda: db_session, event_id=99999) is False
    assert replay_outbox_event(db_factory=lambda: db_session, event_id=ev_id) is False


def test_cli_admin_replay_all(db_session):
    """Valida el reprocesamiento masivo de todos los eventos en DEAD_LETTER."""
    ev1 = OutboxEvent(event_type="invoice.processed", payload="{}", status="DEAD_LETTER")
    ev2 = OutboxEvent(event_type="invoice.processed", payload="{}", status="DEAD_LETTER")
    db_session.add(ev1)
    db_session.add(ev2)
    db_session.commit()

    replayed_count = replay_all_dead_letters(db_factory=lambda: db_session, event_type="invoice.processed")
    assert replayed_count >= 2


def test_cli_admin_main_execution(db_session, capsys):
    """Valida la ejecución del punto de entrada CLI de cajaclara-admin."""
    # List
    code_list = cli_main(["outbox", "list", "--limit", "5"], db_factory=lambda: db_session)
    assert code_list == 0

    # Replay non-existent
    code_replay = cli_main(["outbox", "replay", "--id", "999999"], db_factory=lambda: db_session)
    assert code_replay == 1

    # Replay all
    code_all = cli_main(["outbox", "replay-all"], db_factory=lambda: db_session)
    assert code_all == 0


@pytest.mark.anyio
async def test_notifications_formatting_and_isolation():
    """Valida el formateo de alertas y la tolerancia a fallos en notificaciones."""
    data = {
        "issuer_id": "20601234567",
        "invoice_number": "F001-00012345",
        "total_amount": "1180.00",
        "detail": "RUC no habido",
    }

    # Formateo
    tg_text = format_telegram_alert("fiscal.alert.cdr_rejected", data)
    assert "ALERTA FISCAL CRÍTICA" in tg_text
    assert "20601234567" in tg_text

    wa_text = format_whatsapp_alert("fiscal.alert.cdr_rejected", data)
    assert "ALERTA FISCAL CRÍTICA" in wa_text

    # Simular caída de Telegram (HTTP 500) y verificar que no arroje excepción
    def telegram_down_mock(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Telegram Server Error")

    transport = httpx.MockTransport(telegram_down_mock)
    async with httpx.AsyncClient(transport=transport) as client:
        results = await send_multichannel_notification(
            event_type="fiscal.alert.cdr_rejected",
            alert_payload=data,
            telegram_bot_token="fake_bot_token",
            telegram_chat_id="123456",
            http_client=client,
        )
        assert results["telegram"] is False
