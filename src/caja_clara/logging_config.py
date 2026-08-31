"""
Logging configuration with structlog and PII redaction.
"""

import logging
import re
import sys
from typing import Any

import structlog
from structlog.types import EventDict

# Regex para detección de RUC/DNI en cadenas
RUC_REGEX = re.compile(r"\b(10|20)\d{9}\b")


def _mask_ruc(match: re.Match[str]) -> str:
    val = match.group(0)
    return f"{val[:2]}*******{val[-2:]}"


def redact_pii(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Redact Personally Identifiable Information (PII) from logs universalmente.
    Aplica en todos los niveles (incluido DEBUG) para estricto compliance.
    """
    if "sender_email" in event_dict:
        email = event_dict["sender_email"]
        if email and "@" in str(email):
            local, domain = str(email).split("@", 1)
            event_dict["sender_email"] = f"{local[0]}***{local[-1]}@{domain}" if len(local) > 1 else f"***@{domain}"
        else:
            event_dict["sender_email"] = "***"

    if "issuer_id" in event_dict and event_dict["issuer_id"]:
        issuer = str(event_dict["issuer_id"])
        if len(issuer) == 11:
            event_dict["issuer_id"] = f"{issuer[:2]}*******{issuer[-2:]}"

    if "subject" in event_dict:
        subject = str(event_dict["subject"]) if event_dict["subject"] else ""
        if subject:
            event_dict["subject"] = subject[:20] + " [REDACTED]"

    # Enmascarar RUCs que aparezcan en mensajes o descripciones
    for k, v in list(event_dict.items()):
        if isinstance(v, str) and k not in ("timestamp", "level", "event", "logger"):
            event_dict[k] = RUC_REGEX.sub(_mask_ruc, v)

    # Purgar credenciales y secretos incondicionalmente
    for secret_key in ("password", "imap_password", "api_key", "ai_api_key", "token", "secret"):
        event_dict.pop(secret_key, None)

    return event_dict


def setup_logging(level: str = "INFO") -> None:
    """Configure structlog for JSON output to stdout."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=numeric_level)

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            redact_pii,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
