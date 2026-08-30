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
    "start_time": time.time(),
    "emails_processed_total": 0,
    "emails_errored_total": 0,
    "last_successful_cycle": None,
    "db_size_bytes": 0,
    "imap_connection_status": "disconnected"
}

# Inicializar métricas globales
startup_time = datetime.now(UTC)
emails_processed = 0
emails_errored = 0
last_success = None

def _handle_signal(signum: int, frame: Any) -> None:
    """Manejador de señales de sistema para apagar el demonio limpiamente."""
    logger.info("senal_recibida", signum=signal.Signals(signum).name)
    shutdown_event.set()

def write_status_file() -> None:
    """Escribe el archivo de estado de métricas en formato JSON de forma atómica."""
    global startup_time, emails_processed, emails_errored, last_success

    status_path = config.db_path.replace("cajaclarad.db", "status.json")
    tmp_path = status_path + ".tmp"
    
    try:
        db_size = os.path.getsize(config.db_path) if os.path.exists(config.db_path) else 0
    except Exception:
        db_size = 0

    state = {
        "pid": os.getpid(),
        "uptime_seconds": (datetime.now(UTC) - startup_time).total_seconds(),
        "last_successful_cycle": last_success.isoformat() if last_success else None,
        "emails_processed_total": emails_processed,
        "emails_errored_total": emails_errored,
        "imap_connection_status": "connected", # Simplificado para Fase 1
        "db_size_bytes": db_size
    }

    try:
        with open(tmp_path, "w") as f:
            json.dump(state, f)
        os.replace(tmp_path, status_path)
    except Exception as e:
        logger.warning("error_escribiendo_status", error=str(e))

def process_mailbox(client: IMAPClient) -> None:
    """Ejecuta una iteración completa: conecta a IMAP, procesa no leídos y escribe a BD."""
    global emails_processed, emails_errored, last_success
    
    try:
        client.connect()
    except Exception as e:
        logger.error("error_conexion_imap", error=str(e))
        return

    db_generator = get_db()
    db_session = next(db_generator)

    try:
        for msg in client.fetch_unseen():
            if shutdown_event.is_set():
                break

            logger.info("procesando_correo", uid=msg.uid, subject=msg.subject)
            extract, err = extract_email_data(msg, config.imap_user)
            
            # Iniciar transacción de base de datos
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
                        imap_uid=int(msg.uid),
                        mailbox_account=config.imap_user,
                        sender_email=msg.from_ or "unknown",
                        received_date=msg.date or datetime.now(UTC),
                        subject=msg.subject[:255] if msg.subject else "",
                        has_attachments=bool(msg.attachments),
                        status="ERROR",
                        error_detail=err
                    )
                    db_session.add(record)
                    status_log = "ERROR"
                
                db_session.commit()
                client.mark_seen(msg.uid)
                
                if status_log == "PROCESSED":
                    emails_processed += 1
                elif status_log == "ERROR":
                    emails_errored += 1
                    
                logger.info("correo_guardado_bd", uid=msg.uid, status=status_log)

            except IntegrityError:
                # Violación de Constraint Unique (El message_id ya existe)
                db_session.rollback()
                client.mark_seen(msg.uid)
                logger.debug("correo_duplicado_ignorado", uid=msg.uid)

            except Exception as e:
                db_session.rollback()
                logger.error("error_procesando_correo", uid=msg.uid, error=str(e))

        db_session.commit()
        last_success = datetime.now(UTC)

    except Exception as e:
        logger.error("error_ciclo_general", error=str(e))
        state["imap_connection_status"] = "error"
        raise e
    finally:
        client.logout()
        db_session.close()

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
