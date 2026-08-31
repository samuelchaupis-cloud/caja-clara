"""
Módulo criptográfico para firma y verificación de Webhooks con HMAC-SHA256 y defensa Anti-Replay.
"""

import hashlib
import hmac
import time


def sign_webhook_payload(payload: str, secret: str, timestamp: int | None = None) -> tuple[str, int]:
    """
    Calcula la firma criptográfica HMAC-SHA256 para un payload de Webhook.
    Retorna la cabecera formateada (t=...,v1=...) y el timestamp UNIX.
    """
    ts = timestamp if timestamp is not None else int(time.time())
    to_sign = f"v1:{ts}:{payload}"
    signature = hmac.new(secret.encode("utf-8"), to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    header_val = f"t={ts},v1={signature}"
    return header_val, ts


def verify_webhook_signature(
    payload: str,
    signature_header: str,
    secret: str,
    tolerance_seconds: int = 300,
    current_time: int | None = None,
) -> bool:
    """
    Valida la firma de un Webhook y verifica que la marca de tiempo esté dentro de la ventana de tolerancia.
    """
    if not signature_header or not secret:
        return False

    parts = dict(item.split("=", 1) for item in signature_header.split(",") if "=" in item)
    if "t" not in parts or "v1" not in parts:
        return False

    try:
        ts = int(parts["t"])
        expected_sig = parts["v1"]
    except (ValueError, KeyError):
        return False

    # Verificación Anti-Replay
    now = current_time if current_time is not None else int(time.time())
    if abs(now - ts) > tolerance_seconds:
        return False

    # Verificación de Firma con tiempo constante (previene timing attacks)
    to_sign = f"v1:{ts}:{payload}"
    computed_sig = hmac.new(secret.encode("utf-8"), to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed_sig, expected_sig)
