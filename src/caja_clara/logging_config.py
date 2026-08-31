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


SECRET_KEY_PATTERNS = ("password", "secret", "token", "key", "auth", "credential", "signature", "litestream", "pass")


def _is_secret_key(key: str) -> bool:
    key_lower = key.lower()
    return any(pattern in key_lower for pattern in SECRET_KEY_PATTERNS)


def _sanitize_value(val: Any) -> Any:
    if isinstance(val, dict):
        return {k: _sanitize_value(v) for k, v in val.items() if not _is_secret_key(str(k))}
    if isinstance(val, list):
        return [_sanitize_value(item) for item in val]
    if isinstance(val, str):
        return RUC_REGEX.sub(_mask_ruc, val)
    return val


def redact_pii(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Redact Personally Identifiable Information (PII) and cloud secrets from logs.
    Aplica de forma recursiva en todos los niveles (incluido DEBUG) para estricto compliance.
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

    # Sanitizar y purgar claves sensibles y estructuras anidadas
    keys_to_delete = [k for k in event_dict if _is_secret_key(k)]
    for k in keys_to_delete:
        event_dict.pop(k, None)

    # Sanitizar recursivamente los valores restantes
    for k, v in list(event_dict.items()):
        if k not in ("timestamp", "level", "event", "logger"):
            event_dict[k] = _sanitize_value(v)

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
