"""
Orquestador y Supervisor de Concurrencia Multi-Buzón (MailboxPoolOrchestrator).
Permite ingesta paralela de múltiples cuentas IMAP con aislamiento estricto de fallos (N-1 Inmunes).
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from caja_clara.database import SessionLocal
from caja_clara.extractor import extract_email_data
from caja_clara.fiscal_alerts import build_canonical_erp_payload, evaluate_fiscal_alerts
from caja_clara.imap_client import IMAPClient
from caja_clara.metrics import (
    INVOICES_TOTAL,
    MAILBOX_INVOICES_TOTAL,
    MAILBOX_STATUS,
    PROCESSING_DURATION_SECONDS,
)
from caja_clara.models import InvoiceRecord, OutboxEvent

logger = structlog.get_logger(__name__)


@dataclass
class MailboxConfig:
    account_id: str
    host: str
    port: int
    user: str
    password: str | None = None
    oauth2_token: str | None = None
    poll_interval: int = 15


class MailboxWorker(threading.Thread):
    """Worker supervisado para un buzón IMAP específico."""

    def __init__(
        self,
        mailbox_config: MailboxConfig,
        db_factory: Callable[[], Session] = SessionLocal,
        client: IMAPClient | None = None,
        shutdown_event: threading.Event | None = None,
    ) -> None:
        super().__init__(name=f"MailboxWorker-{mailbox_config.account_id}", daemon=True)
        self.config = mailbox_config
        self.db_factory = db_factory
        self.client = client or IMAPClient(
            host=mailbox_config.host,
            port=mailbox_config.port,
            user=mailbox_config.user,
            password=mailbox_config.password,
            oauth2_token=mailbox_config.oauth2_token,
        )
        self.shutdown_event = shutdown_event or threading.Event()
        self.state: str = "INITIALIZING"
        self.consecutive_errors: int = 0

    def run(self) -> None:
        """Bucle de ejecución y supervisión continua del worker."""
        logger.info("iniciando_worker_buzon", account=self.config.account_id)
        MAILBOX_STATUS.labels(mailbox=self.config.account_id).set(0)

        while not self.shutdown_event.is_set():
            try:
                self.process_cycle()
                self.consecutive_errors = 0
            except Exception as e:
                self.consecutive_errors += 1
                self.state = "DEGRADED" if self.consecutive_errors < 5 else "SUSPENDED"
                MAILBOX_STATUS.labels(mailbox=self.config.account_id).set(0)
                logger.error(
                    "error_ciclo_worker_buzon",
                    account=self.config.account_id,
                    state=self.state,
                    consecutive_errors=self.consecutive_errors,
                    error=str(e),
                )

                # Backoff según severidad
                sleep_time = min(60, 5 * self.consecutive_errors)
                self.shutdown_event.wait(timeout=sleep_time)

        self._cleanup()

    def process_cycle(self) -> int:
        """Ejecuta un ciclo de conexión, descarga, extracción y persistencia atómica."""
        processed_count = 0
        try:
            self.client.connect()
            self.state = "SYNCING"
            MAILBOX_STATUS.labels(mailbox=self.config.account_id).set(1)

            for msg in self.client.fetch_unseen():
                if self.shutdown_event.is_set():
                    break

                t0 = time.perf_counter()
                status_log = "ERROR"
                parser_used = "unknown"

                # Fase 1: Red y Parseo en Memoria (CERO LOCK DE BD)
                extract, err = extract_email_data(msg, self.config.account_id)
                if extract:
                    parser_used = "xml_ubl" if (extract.attachment_filename or "").lower().endswith((".xml", ".zip")) else "pdf"

                # Fase 2: Persistencia Atómica < 2ms con BEGIN IMMEDIATE
                with self.db_factory() as session:
                    try:
                        if extract:
                            # Chequeo de duplicados
                            existing = (
                                session.query(InvoiceRecord)
                                .filter(
                                    (InvoiceRecord.message_id == extract.message_id)
                                    | ((InvoiceRecord.attachment_hash == extract.attachment_hash) & (InvoiceRecord.attachment_hash.isnot(None)))
                                )
                                .first()
                            )

                            if existing:
                                record = InvoiceRecord(
                                    message_id=extract.message_id,
                                    imap_uid=extract.imap_uid,
                                    mailbox_account=self.config.account_id,
                                    sender_email=extract.sender_email,
                                    received_date=extract.received_date,
                                    subject=extract.subject,
                                    has_attachments=extract.has_attachments,
                                    attachment_filename=extract.attachment_filename,
                                    attachment_hash=extract.attachment_hash,
                                    attachment_size_bytes=extract.attachment_size_bytes,
                                    status="DUPLICATE",
                                    error_detail=f"Duplicado detectado (coincide con registro id={existing.id})",
                                )
                                session.add(record)
                                status_log = "DUPLICATE"
                            else:
                                dump_data = extract.model_dump()
                                dump_data["status"] = "PROCESSED"
                                record = InvoiceRecord(**dump_data)
                                session.add(record)

                                # Generar Outbox Event
                                canonical = build_canonical_erp_payload(record)
                                outbox_event = OutboxEvent(
                                    event_type="invoice.processed",
                                    payload=json.dumps(canonical, default=str),
                                    status="PENDING",
                                )
                                session.add(outbox_event)

                                # Generar Alertas Fiscales
                                for alert in evaluate_fiscal_alerts(record):
                                    session.add(alert)

                                status_log = "PROCESSED"
                        else:
                            record = InvoiceRecord(
                                message_id=msg.headers.get("message-id", (f"<{msg.uid}@unknown>",))[0],
                                imap_uid=int(msg.uid or 0),
                                mailbox_account=self.config.account_id,
                                sender_email=msg.from_ or "unknown",
                                received_date=msg.date or datetime.now(UTC),
                                subject=msg.subject[:255] if msg.subject else "",
                                has_attachments=bool(msg.attachments),
                                status="ERROR",
                                error_detail=err,
                            )
                            session.add(record)
                            status_log = "ERROR"

                        session.commit()
                        processed_count += 1

                        # Fase 3: Acknowledgment en Red
                        if msg.uid is not None:
                            self.client.mark_seen(str(msg.uid))

                        # Métricas
                        duration = time.perf_counter() - t0
                        PROCESSING_DURATION_SECONDS.labels(parser=parser_used, status=status_log).observe(duration)
                        doc_type = record.document_type or "01"
                        curr = record.currency or "PEN"
                        INVOICES_TOTAL.labels(status=status_log, document_type=doc_type, currency=curr).inc()
                        MAILBOX_INVOICES_TOTAL.labels(
                            mailbox=self.config.account_id,
                            status=status_log,
                            document_type=doc_type,
                            currency=curr,
                        ).inc()

                    except IntegrityError:
                        session.rollback()
                        if msg.uid is not None:
                            self.client.mark_seen(str(msg.uid))

            self.state = "IDLE"
        finally:
            self.client.logout()

        return processed_count

    def _cleanup(self) -> None:
        """Limpieza y desconexión segura al apagar el worker."""
        MAILBOX_STATUS.labels(mailbox=self.config.account_id).set(0)
        self.state = "STOPPED"
        self.client.logout()
        logger.info("worker_buzon_detenido", account=self.config.account_id)


class MailboxPoolOrchestrator:
    """Supervisor general que gestiona el ciclo de vida de N workers de buzones."""

    def __init__(
        self,
        mailboxes: list[MailboxConfig],
        db_factory: Callable[[], Session] = SessionLocal,
    ) -> None:
        self.mailboxes = mailboxes
        self.db_factory = db_factory
        self.shutdown_event = threading.Event()
        self.workers: dict[str, MailboxWorker] = {}

    def start(self) -> None:
        """Inicia todos los workers de buzones en hilos independientes."""
        logger.info("iniciando_mailbox_pool_orchestrator", total_mailboxes=len(self.mailboxes))
        for mbox in self.mailboxes:
            worker = MailboxWorker(
                mailbox_config=mbox,
                db_factory=self.db_factory,
                shutdown_event=self.shutdown_event,
            )
            self.workers[mbox.account_id] = worker
            worker.start()

    def stop(self) -> None:
        """Señaliza apagado ordenado a todos los workers y espera su finalización."""
        logger.info("deteniendo_mailbox_pool_orchestrator")
        self.shutdown_event.set()
        for worker in self.workers.values():
            worker.join(timeout=10)
        logger.info("mailbox_pool_orchestrator_detenido")

    def get_status(self) -> dict[str, Any]:
        """Reporta el estado en tiempo real de todos los workers supervisados."""
        return {
            account_id: {
                "state": worker.state,
                "consecutive_errors": worker.consecutive_errors,
                "is_alive": worker.is_alive(),
            }
            for account_id, worker in self.workers.items()
        }
