"""
Módulo del despachador asíncrono de eventos outbox (Transactional Outbox Pattern).
"""

from __future__ import annotations

import asyncio
import secrets
import signal
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import structlog
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from caja_clara.config import config
from caja_clara.crypto import sign_webhook_payload
from caja_clara.database import SessionLocal, engine, verify_db_integrity, verify_schema_version
from caja_clara.logging_config import setup_logging
from caja_clara.metrics import (
    OUTBOX_DELIVERY_DURATION_SECONDS,
    OUTBOX_DELIVERY_RETRIES_TOTAL,
    OUTBOX_EVENTS_TOTAL,
)
from caja_clara.models import OutboxEvent

logger = structlog.get_logger(__name__)


class OutboxDispatcher:
    """Worker asíncrono para despacho resiliente de eventos con firmas criptográficas."""

    def __init__(
        self,
        db_factory: Callable[[], Session],
        http_client: httpx.AsyncClient | None = None,
        target_url: str | None = None,
        webhook_secret: str | None = None,
        max_retries: int = 5,
        base_delay: float = 2.0,
        max_delay: float = 300.0,
        max_concurrent: int = 5,
    ) -> None:
        self.db_factory = db_factory
        self._external_client = http_client
        self.target_url: str = str(target_url or getattr(config, "webhook_url", "http://localhost:8000/api/v1/webhooks"))
        self.webhook_secret: str = str(webhook_secret or getattr(config, "api_key", "default_secret"))
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._external_client is not None:
            return self._external_client
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=20, keepalive_expiry=30.0)
        timeout = httpx.Timeout(timeout=10.0, connect=5.0)
        return httpx.AsyncClient(limits=limits, timeout=timeout)

    async def process_batch(self, limit: int = 25) -> int:
        """Sondea y despacha un lote acotado de eventos en estado PENDING."""
        now = datetime.now(UTC)
        claimed: list[tuple[int, str, str, int]] = []

        # Fase 1: Reclamo atómico y ultracorto en BD (BEGIN IMMEDIATE)
        with self.db_factory() as session:
            stmt = (
                select(OutboxEvent)
                .where(
                    OutboxEvent.status == "PENDING",
                    or_(OutboxEvent.next_retry_at.is_(None), OutboxEvent.next_retry_at <= now),
                )
                .order_by(OutboxEvent.id.asc())
                .limit(limit)
            )
            events = session.execute(stmt).scalars().all()
            if not events:
                return 0

            for e in events:
                claimed.append((e.id, e.event_type, e.payload, e.retry_count))
                e.status = "PROCESSING"
            session.commit()

        # Fase 2: Despacho HTTP concurrente fuera de cualquier transacción de BD
        client = await self._get_client()
        tasks = [self._dispatch_event(client, item) for item in claimed]
        await asyncio.gather(*tasks, return_exceptions=True)

        if self._external_client is None:
            await client.aclose()

        return len(claimed)

    async def _dispatch_event(self, client: httpx.AsyncClient, item: tuple[int, str, str, int]) -> None:
        event_id, event_type, payload, retry_count = item
        async with self.semaphore:
            start_time = time.perf_counter()
            ts = int(time.time())
            signature_header, _ = sign_webhook_payload(payload, self.webhook_secret, timestamp=ts)

            headers = {
                "Content-Type": "application/json",
                "User-Agent": "CajaClara-OutboxDispatcher/1.0",
                "X-CajaClara-Event-Id": str(event_id),
                "X-CajaClara-Event-Type": event_type,
                "X-CajaClara-Signature": signature_header,
            }

            status_result = "unknown"
            error_message: str | None = None
            is_transient = False
            is_fatal = False

            try:
                response = await client.post(
                    self.target_url,
                    content=payload.encode("utf-8"),
                    headers=headers,
                )
                duration = time.perf_counter() - start_time

                if response.is_success:
                    status_result = "success"
                    OUTBOX_DELIVERY_DURATION_SECONDS.labels(event_type=event_type, status="success").observe(duration)
                    OUTBOX_EVENTS_TOTAL.labels(event_type=event_type, status="success").inc()
                elif 400 <= response.status_code < 500 and response.status_code != 429:
                    is_fatal = True
                    status_result = "dead_letter"
                    error_message = f"HTTP {response.status_code}: {response.text[:255]}"
                    OUTBOX_DELIVERY_DURATION_SECONDS.labels(event_type=event_type, status="client_error").observe(duration)
                    OUTBOX_EVENTS_TOTAL.labels(event_type=event_type, status="dead_letter").inc()
                else:
                    is_transient = True
                    status_result = "transient_error"
                    error_message = f"HTTP {response.status_code}: {response.text[:255]}"
                    OUTBOX_DELIVERY_DURATION_SECONDS.labels(event_type=event_type, status="server_error").observe(duration)
            except Exception as exc:
                duration = time.perf_counter() - start_time
                is_transient = True
                status_result = "transient_error"
                error_message = f"Transport error: {exc}"
                OUTBOX_DELIVERY_DURATION_SECONDS.labels(event_type=event_type, status="network_error").observe(duration)

            # Fase 3: Liquidación atómica en BD
            with self.db_factory() as session:
                ev = session.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()
                if ev is None:
                    return

                if status_result == "success":
                    ev.status = "DELIVERED"
                    ev.processed_at = datetime.now(UTC)
                    ev.error_detail = None
                    logger.info("outbox_evento_despachado", event_id=event_id, event_type=event_type)
                elif is_fatal:
                    ev.status = "DEAD_LETTER"
                    ev.error_detail = error_message
                    logger.warning("outbox_error_fatal_cliente", event_id=event_id, error=error_message)
                elif is_transient:
                    new_retry_count = retry_count + 1
                    if new_retry_count <= self.max_retries:
                        jitter = secrets.SystemRandom().uniform(0.1, 0.5)
                        delay = min(self.max_delay, self.base_delay * (2**retry_count)) + jitter
                        ev.status = "PENDING"
                        ev.retry_count = new_retry_count
                        ev.next_retry_at = datetime.now(UTC) + timedelta(seconds=delay)
                        ev.error_detail = error_message
                        OUTBOX_DELIVERY_RETRIES_TOTAL.labels(event_type=event_type).inc()
                        OUTBOX_EVENTS_TOTAL.labels(event_type=event_type, status="transient_error").inc()
                        logger.warning("outbox_reintento_programado", event_id=event_id, delay_seconds=delay, error=error_message)
                    else:
                        ev.status = "DEAD_LETTER"
                        ev.error_detail = f"Max reintentos superados ({self.max_retries}): {error_message}"
                        OUTBOX_EVENTS_TOTAL.labels(event_type=event_type, status="dead_letter").inc()
                        logger.error("outbox_max_reintentos_superado", event_id=event_id, error=error_message)

                session.commit()

    async def run_forever(self, poll_interval: float = 2.0, shutdown_event: asyncio.Event | None = None) -> None:
        """Bucle principal de ejecución del dispatcher."""
        logger.info("iniciando_outbox_dispatcher", target_url=self.target_url)
        while shutdown_event is None or not shutdown_event.is_set():
            try:
                processed = await self.process_batch()
                if processed == 0:
                    await asyncio.sleep(poll_interval)
            except Exception as e:
                logger.error("error_ciclo_dispatcher", error=str(e))
                await asyncio.sleep(poll_interval)


def main():
    """Punto de entrada de CLI para el demonio dispatcher."""
    setup_logging(config.log_level)
    logger.info("arrancando_servicio_dispatcher")

    try:
        verify_db_integrity(engine)
        verify_schema_version(engine)
    except Exception as e:
        logger.critical("arranque_dispatcher_fallido", error=str(e))
        sys.exit(1)

    dispatcher = OutboxDispatcher(db_factory=SessionLocal)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    shutdown_ev = asyncio.Event()

    def _sig_handler(sig: int, _frame: Any) -> None:
        logger.info("senal_recibida_dispatcher", signal=signal.Signals(sig).name)
        shutdown_ev.set()

    signal.signal(signal.SIGTERM, _sig_handler)
    signal.signal(signal.SIGINT, _sig_handler)

    try:
        loop.run_until_complete(dispatcher.run_forever(shutdown_event=shutdown_ev))
    finally:
        loop.close()
        logger.info("dispatcher_detenido")


if __name__ == "__main__":
    main()
