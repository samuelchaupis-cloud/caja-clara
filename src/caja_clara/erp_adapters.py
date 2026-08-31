"""
Módulo de adaptadores y transformadores de Esquema Canónico ERP v1 hacia sistemas contables.
Soporta generación de asientos borrador para Odoo (v16/v17), SAP Business One (Service Layer v2) y Siigo Cloud.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def _to_decimal(val: str | int | float | Decimal | None) -> Decimal:
    """Convierte cualquier valor numérico a Decimal sin pérdida de precisión."""
    if val is None:
        return Decimal("0.00")
    return Decimal(str(val))


def transform_to_odoo_invoice(canonical_payload: dict[str, Any]) -> dict[str, Any]:
    """
    Transforma el esquema canónico JSON de CajaClara a la estructura de asiento borrador (account.move) de Odoo.
    Soporta facturas estándar (in_invoice) y notas de crédito de proveedor (in_refund).
    """
    doc = canonical_payload.get("document", {})
    party = canonical_payload.get("party", {})
    acct = canonical_payload.get("accounting", {})
    detraction = acct.get("detraction", {})

    sunat_type = doc.get("sunat_type", "01")
    move_type = "in_refund" if sunat_type == "07" else "in_invoice"

    subtotal = _to_decimal(acct.get("subtotal"))
    tax_amount = _to_decimal(acct.get("tax_amount"))
    total = _to_decimal(acct.get("total_amount"))

    payment_ref = f"Comprobante {doc.get('full_number', '')}"
    if detraction.get("is_subject"):
        payment_ref += f" | SPOT {detraction.get('rate_percentage', '0')}%: S/ {detraction.get('amount', '0.00')}"

    return {
        "model": "account.move",
        "method": "create",
        "values": {
            "move_type": move_type,
            "ref": doc.get("full_number"),
            "partner_vat": party.get("issuer_ruc"),
            "partner_name": party.get("issuer_legal_name"),
            "invoice_date": doc.get("issue_date"),
            "currency_id": doc.get("currency", "PEN"),
            "payment_reference": payment_ref,
            "invoice_line_ids": [
                {
                    "name": f"Adquisición s/g {doc.get('full_number')}",
                    "quantity": 1,
                    "price_unit": f"{subtotal:.2f}",
                    "tax_amount": f"{tax_amount:.2f}",
                    "price_total": f"{total:.2f}",
                }
            ],
            "cajaclara_message_id": canonical_payload.get("origin", {}).get("message_id"),
        },
    }


def transform_to_sap_b1_invoice(canonical_payload: dict[str, Any]) -> dict[str, Any]:
    """
    Transforma el esquema canónico JSON a la estructura de PurchaseInvoices de SAP Business One (Service Layer v2).
    Incluye campos de usuario (UDFs) peruanos para Detracciones SPOT.
    """
    doc = canonical_payload.get("document", {})
    party = canonical_payload.get("party", {})
    acct = canonical_payload.get("accounting", {})
    detraction = acct.get("detraction", {})

    subtotal = _to_decimal(acct.get("subtotal"))
    is_subject = bool(detraction.get("is_subject"))

    return {
        "DocType": "dDocument_Items",
        "CardCode": f"P{party.get('issuer_ruc', '')}",
        "CardName": party.get("issuer_legal_name"),
        "NumAtCard": doc.get("full_number"),
        "DocDate": doc.get("issue_date"),
        "DocDueDate": doc.get("issue_date"),
        "DocCurrency": doc.get("currency", "PEN"),
        "Comments": f"Ingesta automática CajaClara - MessageID: {canonical_payload.get('origin', {}).get('message_id')}",
        "DocumentLines": [
            {
                "ItemCode": "ITEM-GEN-GASTO",
                "ItemDescription": f"Compra s/g {doc.get('full_number')}",
                "Quantity": 1.0,
                "LineTotal": float(subtotal),
                "TaxCode": "IGV_18",
            }
        ],
        "U_BKP_SunatType": doc.get("sunat_type", "01"),
        "U_BKP_Detraccion": "Y" if is_subject else "N",
        "U_BKP_TasaDetracc": str(detraction.get("rate_percentage") or "0.00"),
        "U_BKP_MontoDetracc": str(detraction.get("amount") or "0.00"),
        "U_BKP_NetoPagar": str(detraction.get("net_payable_to_vendor") or acct.get("total_amount") or "0.00"),
    }


def transform_to_siigo_invoice(canonical_payload: dict[str, Any]) -> dict[str, Any]:
    """
    Transforma el esquema canónico JSON a la estructura de Factura de Compra REST API de Siigo Cloud.
    """
    doc = canonical_payload.get("document", {})
    party = canonical_payload.get("party", {})
    acct = canonical_payload.get("accounting", {})
    detraction = acct.get("detraction", {})

    subtotal = _to_decimal(acct.get("subtotal"))
    tax_amount = _to_decimal(acct.get("tax_amount"))

    retentions = []
    if detraction.get("is_subject") and detraction.get("amount"):
        retentions.append(
            {
                "id": 4,  # Código de retención SPOT en catálogo Siigo
                "name": "Detracción SPOT",
                "value": str(detraction.get("amount")),
                "percentage": str(detraction.get("rate_percentage") or "0.00"),
            }
        )

    return {
        "document": {"id": 24},  # Documento estándar de compra de proveedor
        "date": doc.get("issue_date"),
        "customer": {
            "identification": party.get("issuer_ruc"),
            "branch_office": 0,
        },
        "cost_center": 1,
        "observations": f"Importado por CajaClara | {doc.get('full_number')}",
        "items": [
            {
                "code": "SERV-01",
                "description": f"Factura proveedor {doc.get('full_number')}",
                "quantity": 1,
                "price": f"{subtotal:.2f}",
                "taxes": [{"id": 1, "value": f"{tax_amount:.2f}"}],
            }
        ],
        "retentions": retentions,
        "payments": [
            {
                "id": 1,
                "value": str(detraction.get("net_payable_to_vendor") or acct.get("total_amount") or "0.00"),
                "due_date": doc.get("issue_date"),
            }
        ],
    }
