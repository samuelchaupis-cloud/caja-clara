"""
Main daemon orchestration module.
Handles signals, main event loop, and ties components together.
"""
import json
import os
import signal
import sys
import threading
import time
from datetime import UTC, datetime

import sdnotify
import structlog
from sqlalchemy.exc import IntegrityError

from caja_clara.config import config
from caja_clara.database import engine, get_db, verify_db_integrity, verify_schema_version
from caja_clara.extractor import extract_email_data
from caja_clara.imap_client import IMAPClient
from caja_clara.logging_config import setup_logging
from caja_clara.models import InvoiceRecord

logger = structlog.get_logger(__name__)
shutdown_event = threading.Event()

# Metrics
state = {
    "pid": os.getpid(),
    "start_time": time.time(),
    "last_successful_cycle": None,
    "emails_processed_total": 0,
    "emails_errored_total": 0,
    "imap_connection_status": "disconnected"
}

def _handle_signal(signum, frame):
    """Handle termination signals gracefully."""
    logger.info("señal_recibida", signal=signal.Signals(signum).name)
    shutdown_event.set()

def write_status_file():
    """Write metrics atomically to status.json."""
    state["uptime_seconds"] = int(time.time() - state["start_time"])
    try:
        db_size = os.path.getsize(config.db_path) if os.path.exists(config.db_path) else 0
    except Exception:
        db_size = 0
        
    state["db_size_bytes"] = db_size

    status_path = "/var/lib/cajaclarad/status.json"
    if not os.path.exists("/var/lib/cajaclarad"):
        # local dev fallback
        status_path = "status.json"

    tmp_path = f"{status_path}.tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(state, f)
        os.replace(tmp_path, status_path)
    except Exception as e:
        logger.warning("error_escribiendo_status", error=str(e))

def process_mailbox(client: IMAPClient):
    """Fetch unread emails, extract, validate, and store."""
    try:
        if not client._mailbox:
            client.connect()
            state["imap_connection_status"] = "connected"

        db_gen = get_db()
        db_session = next(db_gen)
        
        for msg in client.fetch_unseen():
            if shutdown_event.is_set():
                break

            start_t = time.time()
            extract, err = extract_email_data(msg, config.imap_user)
            
            # Start database transaction
            db_session.begin_nested()
            try:
                if extract:
                    # Fase 2.2: Verificación de deduplicación por attachment_hash
                    duplicate = False
                    if extract.attachment_hash:
                        existing = db_session.query(InvoiceRecord).filter_by(
                            attachment_hash=extract.attachment_hash
                        ).first()
                        if existing:
                            duplicate = True
                            
                    if duplicate:
                        # Se registra pero con estado DUPLICATE para tener trazabilidad
                        record = InvoiceRecord(**extract.model_dump())
                        record.status = "DUPLICATE"
                        record.error_detail = "Factura ya ingresada previamente (hash duplicado)"
                        db_session.add(record)
                        status_log = "DUPLICATE"
                    else:
                        # Flujo normal
                        record = InvoiceRecord(**extract.model_dump())
                        db_session.add(record)
                        status_log = "PROCESSED"
                else:
                    record = InvoiceRecord(
                        message_id=msg.headers.get("message-id", (f"<{msg.uid}@unknown>",))[0],
                        imap_uid=msg.uid,
                        mailbox_account=config.imap_user,
                        sender_email=msg.from_ or "unknown",
                        received_date=msg.date or datetime.now(UTC),
                        status="ERROR",
                        error_detail=err
                    )
                    db_session.add(record)
                    status_log = "ERROR"
                    state["emails_errored_total"] += 1
                
                db_session.commit()
                # If commit succeeds, mark as seen in IMAP
                client.mark_seen(msg.uid)
                
                if extract:
                    state["emails_processed_total"] += 1

                logger.info(
                    "correo_procesado",
                    message_id=record.message_id,
                    sender_email=record.sender_email,
                    status=status_log,
                    duration_ms=int((time.time() - start_t) * 1000)
                )

            except IntegrityError:
                # Deduplication logic: duplicate message_id
                db_session.rollback()
                client.mark_seen(msg.uid)
                logger.debug("correo_duplicado_ignorado", uid=msg.uid)

            except Exception as e:
                db_session.rollback()
                logger.error("error_procesando_correo", uid=msg.uid, error=str(e))
                # Do not mark as seen. It will be retried.
        
        # Final commit for the cycle
        db_session.commit()
        state["last_successful_cycle"] = datetime.now(UTC).isoformat()
        
    except Exception as e:
        logger.error("error_ciclo_principal", error=str(e))
        state["imap_connection_status"] = "error"
        raise

def main():
    """Main entrypoint for the daemon."""
    setup_logging(config.log_level)
    logger.info("iniciando_cajaclarad", version="0.1.0")

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    try:
        verify_db_integrity(engine)
        verify_schema_version(engine)
    except Exception as e:
        logger.critical("arranque_fallido", error=str(e))
        sys.exit(1)

    client = IMAPClient()
    notifier = sdnotify.SystemdNotifier()
    notifier.notify("READY=1")

    while not shutdown_event.is_set():
        try:
            process_mailbox(client)
        except Exception:
            pass # Already logged inside process_mailbox
        
        write_status_file()
        notifier.notify("WATCHDOG=1")
        
        # Fase 2.4: Usar IDLE para esperar eventos (o sleep si falla)
        # El timeout lo combinamos con poll_interval para despertar el watchdog
        try:
            client.wait_for_new_messages(timeout=config.poll_interval)
        except Exception:
            shutdown_event.wait(timeout=config.poll_interval)

    # Clean shutdown sequence
    logger.info("apagado_iniciado")
    client.logout()
    logger.info("apagado_completado")
    sys.exit(0)

if __name__ == "__main__":
    main()
