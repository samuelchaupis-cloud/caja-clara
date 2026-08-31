import time

from caja_clara.crypto import sign_webhook_payload, verify_webhook_signature


def test_sign_and_verify_webhook_payload():
    """Valida la generación de firma HMAC-SHA256 y verificación exitosa."""
    payload = '{"event": "invoice.processed", "id": "123"}'
    secret = "whsec_super_secret_enterprise_key"

    header_sig, ts = sign_webhook_payload(payload, secret)

    assert "t=" in header_sig
    assert "v1=" in header_sig

    # Verificación válida
    assert verify_webhook_signature(payload, header_sig, secret, tolerance_seconds=300) is True

    # Verificación fallida con payload adulterado
    tampered_payload = '{"event": "invoice.processed", "id": "123", "hacked": true}'
    assert verify_webhook_signature(tampered_payload, header_sig, secret) is False

    # Verificación fallida con secreto incorrecto
    assert verify_webhook_signature(payload, header_sig, "wrong_secret") is False


def test_webhook_anti_replay_window():
    """Valida el rechazo de eventos cuya marca de tiempo excede la ventana de tolerancia."""
    payload = '{"event": "test"}'
    secret = "whsec_test"
    old_timestamp = int(time.time()) - 600  # 10 minutos en el pasado

    header_sig, _ = sign_webhook_payload(payload, secret, timestamp=old_timestamp)

    # Debe ser rechazado porque supera los 300 segundos por defecto
    assert verify_webhook_signature(payload, header_sig, secret, tolerance_seconds=300) is False
