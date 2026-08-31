"""
Pipeline for email extraction, attachment processing and data sanitization.
Supports ZIP archives, XML UBL 2.1, PDF and CDR verification.
"""

import hashlib
import io
import zipfile
from datetime import UTC, datetime
from typing import Any

import structlog
from imap_tools import MailMessage
from pydantic import ValidationError

from caja_clara.constants import ALLOWED_ATTACHMENT_EXTENSIONS, MAX_ATTACHMENT_SIZE_BYTES
from caja_clara.parsers.pdf_parser import parse_pdf_invoice
from caja_clara.parsers.xml_parser import parse_cdr_xml, parse_xml_invoice
from caja_clara.schemas import EmailExtract

logger = structlog.get_logger()

# Constantes de seguridad para descompresión de ZIP (Anti-ZipBomb)
MAX_ZIP_FILES = 20
MAX_UNCOMPRESSED_ZIP_SIZE = 10 * 1024 * 1024  # 10 MB


def hash_attachment(payload: bytes) -> str:
    """Generate SHA-256 hash of the attachment content."""
    return hashlib.sha256(payload).hexdigest()


def _process_zip_payload(payload: bytes) -> tuple[dict[str, Any], str | None]:
    """
    Descomprime de forma segura un archivo .zip en memoria y extrae datos de comprobantes XML y CDRs.
    """
    parsed_data: dict[str, Any] = {}
    cdr_data: dict[str, Any] = {}

    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            namelist = z.namelist()

            if len(namelist) > MAX_ZIP_FILES:
                return {}, "El archivo ZIP contiene demasiados ficheros (posible Zip Bomb)"

            total_uncompressed_size = sum(z.getinfo(name).file_size for name in namelist)
            if total_uncompressed_size > MAX_UNCOMPRESSED_ZIP_SIZE:
                return {}, "El contenido descomprimido del ZIP excede el límite de 10MB"

            xml_invoice_bytes: bytes | None = None
            cdr_bytes: bytes | None = None
            total_extracted_bytes = 0
            CHUNK_SIZE = 64 * 1024

            for name in namelist:
                # Prevenir path traversal en nombres de archivos internos
                if ".." in name or name.startswith(("/", "\\")):
                    continue

                clean_name = name.lower()
                if clean_name.endswith(".xml"):
                    content_chunks = []
                    with z.open(name) as f:
                        while chunk := f.read(CHUNK_SIZE):
                            total_extracted_bytes += len(chunk)
                            if total_extracted_bytes > MAX_UNCOMPRESSED_ZIP_SIZE:
                                return {}, "El contenido descomprimido del ZIP excede el límite de 10MB"
                            content_chunks.append(chunk)
                    content = b"".join(content_chunks)

                    # Comprobar si es un CDR (usualmente empieza por R- o contiene CDR/ApplicationResponse)
                    if clean_name.startswith("r-") or "cdr" in clean_name:
                        cdr_bytes = content
                    else:
                        xml_invoice_bytes = content

            if xml_invoice_bytes:
                parsed_data = parse_xml_invoice(xml_invoice_bytes)

            if cdr_bytes:
                cdr_data = parse_cdr_xml(cdr_bytes)
                if cdr_data.get("status"):
                    parsed_data["cdr_status"] = cdr_data["status"]

    except zipfile.BadZipFile:
        return {}, "Archivo ZIP corrupto o formato no válido"
    except Exception as e:
        logger.warning("error_procesando_zip", error=str(e))
        return {}, f"Error al procesar ZIP: {e!s}"

    return parsed_data, None


def extract_email_data(msg: MailMessage, mailbox_account: str) -> tuple[EmailExtract | None, str | None]:
    """
    Extract and sanitize email metadata into an EmailExtract schema.
    Prioritizes deterministic XML UBL / ZIP processing, falling back to PDF if needed.
    """
    try:
        received_date = msg.date if msg.date else datetime.now(UTC)
        has_attachments = len(msg.attachments) > 0
        attachment_filename = None
        attachment_hash = None
        attachment_size_bytes = None

        raw_data: dict[str, Any] = {}

        if has_attachments:
            # 1. Búsqueda priorizada: XML > ZIP > PDF
            chosen_att = None

            # Prioridad 1: XML directo
            for att in msg.attachments:
                if att.filename and att.filename.lower().endswith(".xml"):
                    chosen_att = att
                    break

            # Prioridad 2: ZIP contenedor
            if not chosen_att:
                for att in msg.attachments:
                    if att.filename and att.filename.lower().endswith(".zip"):
                        chosen_att = att
                        break

            # Prioridad 3: PDF
            if not chosen_att:
                for att in msg.attachments:
                    if att.filename and any(att.filename.lower().endswith(ext) for ext in ALLOWED_ATTACHMENT_EXTENSIONS):
                        chosen_att = att
                        break

            if chosen_att:
                attachment_filename = chosen_att.filename
                attachment_size_bytes = len(chosen_att.payload)

                # Validación de tamaño máximo permitido
                if attachment_size_bytes > MAX_ATTACHMENT_SIZE_BYTES:
                    logger.warning("adjunto_ignorado_por_exceso_tamano", filename=attachment_filename, size=attachment_size_bytes)
                    return None, f"Adjunto excede el límite de seguridad ({MAX_ATTACHMENT_SIZE_BYTES} bytes)"

                attachment_hash = hash_attachment(chosen_att.payload)
                ext = attachment_filename.lower()
                parsed_data: dict[str, Any] = {}

                if ext.endswith(".xml"):
                    parsed_data = parse_xml_invoice(chosen_att.payload)
                elif ext.endswith(".zip"):
                    parsed_data, err = _process_zip_payload(chosen_att.payload)
                    if err:
                        logger.warning("fallo_descompresion_zip", error=err)
                elif ext.endswith(".pdf"):
                    parsed_data = parse_pdf_invoice(chosen_att.payload)

                for k, v in parsed_data.items():
                    if v is not None:
                        raw_data[k] = v

        # Completar campos base del correo
        raw_data.update(
            {
                "message_id": msg.headers.get("message-id", (f"<{msg.uid}@unknown>",))[0],
                "imap_uid": msg.uid,
                "mailbox_account": mailbox_account,
                "sender_email": msg.from_,
                "received_date": received_date,
                "subject": msg.subject,
                "has_attachments": has_attachments,
                "attachment_filename": attachment_filename,
                "attachment_hash": attachment_hash,
                "attachment_size_bytes": attachment_size_bytes,
            }
        )

        validated = EmailExtract(**raw_data)
        return validated, None

    except ValidationError as e:
        err_msg = str(e.errors()[0]["msg"]) if e.errors() else str(e)
        return None, err_msg
    except Exception as e:
        return None, f"Extraction error: {e!s}"
