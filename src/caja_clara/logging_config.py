"""
Logging configuration with structlog and PII redaction.
"""
import logging
import sys

import structlog


def redact_pii(_, __, event_dict):
    """
    Redact Personally Identifiable Information (PII) from logs.
    Applied automatically unless level is DEBUG.
    """
    level = event_dict.get("level", "info").lower()
    
    # Do not redact in debug mode
    if level == "debug":
        return event_dict

    if "sender_email" in event_dict:
        email = event_dict["sender_email"]
        if email:
            if "@" in email:
                local, domain = email.split("@", 1)
                event_dict["sender_email"] = f"{local[0]}***{local[-1]}@{domain}" if len(local) > 1 else "***"
            else:
                event_dict["sender_email"] = "***"

    if "subject" in event_dict:
        subject = event_dict["subject"]
        if subject:
            event_dict["subject"] = subject[:20] + " [REDACTED]"

    # Ensure credentials never slip
    event_dict.pop("password", None)
    event_dict.pop("imap_password", None)

    return event_dict

def setup_logging(level: str = "INFO"):
    """Configure structlog for JSON output to stdout."""
    
    # Map string level to logging level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=numeric_level)

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            redact_pii,
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
