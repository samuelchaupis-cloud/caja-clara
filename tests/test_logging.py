from caja_clara.logging_config import redact_pii, setup_logging


def test_redact_pii_email_and_subject():
    """Valida la sanitización de correos electrónicos, RUCs y truncado de asuntos en los logs."""
    event_dict = {
        "level": "info",
        "sender_email": "juan.perez@empresa-proveedor.com.pe",
        "issuer_id": "20601234567",
        "subject": "A" * 150,
        "message": "Comprobante emitido por RUC 10456789012 con éxito",
        "password": "secret_password",
        "other_field": "safe_value",
    }

    redacted = redact_pii(None, "info", event_dict)

    # Valida ofuscación de email y eliminación de password
    assert redacted["sender_email"] != "juan.perez@empresa-proveedor.com.pe"
    assert "***" in redacted["sender_email"]
    assert "password" not in redacted

    # Valida ofuscación de RUCs (primeros 2 y últimos 2 dígitos visibles)
    assert redacted["issuer_id"] == "20*******67"
    assert "10*******12" in redacted["message"]

    # Valida truncado de asunto con tag [REDACTED]
    assert redacted["subject"].endswith("[REDACTED]")
    assert redacted["other_field"] == "safe_value"


def test_redact_pii_debug_mode_strict():
    """Valida que en modo debug la redacción de PII sea igualmente estricta (sin bypass)."""
    event_dict = {
        "level": "debug",
        "sender_email": "juan.perez@empresa.com",
        "subject": "Asunto sensible",
        "issuer_id": "20555666777",
    }
    redacted = redact_pii(None, "debug", event_dict)
    assert redacted["sender_email"] != "juan.perez@empresa.com"
    assert redacted["issuer_id"] == "20*******77"


def test_redact_pii_cloud_secrets_and_nested():
    """Valida la purga de credenciales S3/R2/Litestream y estructuras anidadas."""
    event_dict = {
        "level": "info",
        "litestream_secret_key": "secret_r2_token_xyz",
        "access_key_id": "AKIA1234567890",
        "nested_config": {
            "s3_token": "hidden_nested_token",
            "safe_param": "visible_value",
            "client_ruc": "20123456789",
        },
        "list_items": [
            {"auth_bearer": "bearer_123", "name": "item_1"},
            "Texto con RUC 10987654321 incluido",
        ],
    }

    redacted = redact_pii(None, "info", event_dict)

    assert "litestream_secret_key" not in redacted
    assert "access_key_id" not in redacted
    assert "s3_token" not in redacted["nested_config"]
    assert redacted["nested_config"]["safe_param"] == "visible_value"
    assert redacted["nested_config"]["client_ruc"] == "20*******89"
    assert "auth_bearer" not in redacted["list_items"][0]
    assert redacted["list_items"][0]["name"] == "item_1"
    assert "10*******21" in redacted["list_items"][1]


def test_setup_logging():
    """Valida la inicialización de structlog sin errores."""
    setup_logging("DEBUG")
    setup_logging("INFO")
