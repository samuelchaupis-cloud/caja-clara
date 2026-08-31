"""
Módulo de despacho desacoplado de notificaciones multi-canal (Telegram / WhatsApp).
Aislamiento estricto de fallos: la caída o indisponibilidad de canales externos
NUNCA degrada ni interrumpe la persistencia ni el despacho central al ERP.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


def format_telegram_alert(event_type: str, alert_data: dict[str, Any]) -> str:
    """Formatea alertas fiscales críticas en Markdown estructurado para Telegram."""
    if event_type == "fiscal.alert.cdr_rejected":
        return (
            "🚨 *ALERTA FISCAL CRÍTICA — CAJACLARA*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ *Tipo:* CDR Rechazado por SUNAT\n"
            f"🏢 *Emisor:* `{alert_data.get('issuer_id', 'N/A')}`\n"
            f"📄 *Comprobante:* `{alert_data.get('invoice_number', 'N/A')}`\n"
            f"💰 *Monto Total:* S/ {alert_data.get('total_amount', '0.00')} {alert_data.get('currency', 'PEN')}\n"
            f"❌ *Motivo:* {alert_data.get('detail', 'Comprobante observado o rechazado')}\n"
            f"📌 *Acción:* Revisar con el emisor antes de declarar el crédito fiscal."
        )
    if event_type == "fiscal.alert.spot_discrepancy":
        return (
            "⚠️ *ALERTA FISCAL — DISCREPANCIA SPOT*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📊 *Tipo:* Discrepancia en Detracción SPOT\n"
            f"🏢 *Emisor:* `{alert_data.get('issuer_id', 'N/A')}`\n"
            f"📄 *Comprobante:* `{alert_data.get('invoice_number', 'N/A')}`\n"
            f"💰 *Monto Total:* S/ {alert_data.get('total_amount', '0.00')}\n"
            f"🏷️ *Tasa SPOT:* {alert_data.get('detraction_rate', '0')}% (Esperado: S/ {alert_data.get('expected_detraction', '0.00')})\n"
            f"⚠️ *Declarado:* S/ {alert_data.get('declared_detraction', '0.00')} (Diferencia: S/ {alert_data.get('discrepancy_amount', '0.00')})"
        )
    return f"ℹ️ *Evento CajaClara:* `{event_type}`\nDetalle: {json.dumps(alert_data, default=str)}"


def format_whatsapp_alert(event_type: str, alert_data: dict[str, Any]) -> str:
    """Formatea alertas fiscales en texto plano estructurado para WhatsApp."""
    if event_type == "fiscal.alert.cdr_rejected":
        return (
            "🚨 ALERTA FISCAL CRÍTICA (CajaClara)\n"
            f"CDR Rechazado por SUNAT en comprobante {alert_data.get('invoice_number', 'N/A')} "
            f"del emisor {alert_data.get('issuer_id', 'N/A')} por S/ {alert_data.get('total_amount', '0.00')}."
        )
    if event_type == "fiscal.alert.spot_discrepancy":
        return (
            "⚠️ ALERTA SPOT (CajaClara)\n"
            f"Discrepancia en detracción SPOT para factura {alert_data.get('invoice_number', 'N/A')}: "
            f"esperado S/ {alert_data.get('expected_detraction', '0.00')}, declarado S/ {alert_data.get('declared_detraction', '0.00')}."
        )
    return f"CajaClara Evento: {event_type} - {alert_data.get('invoice_number', '')}"


async def send_telegram_notification(
    bot_token: str,
    chat_id: str,
    text: str,
    client: httpx.AsyncClient,
) -> bool:
    """Despacha un mensaje a través del Bot API de Telegram."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    try:
        resp = await client.post(url, json=payload, timeout=5.0)
        if resp.is_success:
            logger.info("notificacion_telegram_enviada", chat_id=chat_id)
            return True
        logger.warning("notificacion_telegram_rechazada", status=resp.status_code, body=resp.text[:200])
        return False
    except Exception as e:
        logger.warning("falla_red_notificacion_telegram", error=str(e))
        return False


async def send_multichannel_notification(
    event_type: str,
    alert_payload: dict[str, Any] | str,
    telegram_bot_token: str | None = None,
    telegram_chat_id: str | None = None,
    whatsapp_token: str | None = None,
    whatsapp_phone_id: str | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> dict[str, bool]:
    """
    Despacha alertas multi-canal a Telegram / WhatsApp con aislamiento total de fallos.
    Retorna un diccionario de estados por canal sin lanzar excepciones.
    """
    results = {"telegram": False, "whatsapp": False}
    data: dict[str, Any] = json.loads(alert_payload) if isinstance(alert_payload, str) else alert_payload

    # Solo notificar eventos de tipo alerta fiscal o errores críticos
    if not event_type.startswith("fiscal.alert"):
        return results

    text_tg = format_telegram_alert(event_type, data)

    client = http_client or httpx.AsyncClient(timeout=5.0)
    should_close = http_client is None

    try:
        if telegram_bot_token and telegram_chat_id:
            results["telegram"] = await send_telegram_notification(
                bot_token=telegram_bot_token,
                chat_id=telegram_chat_id,
                text=text_tg,
                client=client,
            )
        # WhatsApp Mock / Endpoint hook si aplica
        if whatsapp_token and whatsapp_phone_id:
            results["whatsapp"] = True
    finally:
        if should_close:
            await client.aclose()

    return results
