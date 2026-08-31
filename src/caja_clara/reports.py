"""
Módulo de generación de reportes contables oficiales y exportación a ERPs.
Soporta el formato oficial SUNAT SIRE / RCE (Registro de Compras Electrónico) y exportación estándar CSV.
"""

import csv
import io
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from caja_clara.models import InvoiceRecord


def _format_decimal(val: Decimal | float | None) -> str:
    if val is None:
        return "0.00"
    return f"{Decimal(str(val)):.2f}"


def _format_date(val: datetime | None, fmt: str = "%d/%m/%Y") -> str:
    if val is None:
        return ""
    return val.strftime(fmt)


def generate_sire_rce(invoices: Sequence[InvoiceRecord]) -> str:
    """
    Genera el archivo plano estructurado del Registro de Compras Electrónico (SIRE / RCE - SUNAT).
    Formato delimitado por barras (|) compatible con la macro y validador de SUNAT.
    """
    lines: list[str] = []

    # Cabecera estándar SIRE Compras
    # Estructura resumida de campos clave para conciliación de compras RCE:
    for inv in invoices:
        if inv.status not in ("PROCESSED", "DUPLICATE") and not inv.issuer_id:
            continue

        doc_type = inv.document_type or "01"
        inv_num = inv.invoice_number or "E001-1"
        if "-" in inv_num:
            serie, corr = inv_num.split("-", 1)
        else:
            serie, corr = "E001", inv_num

        ruc = inv.issuer_id or "00000000000"
        name = (inv.issuer_name or "").replace("|", "")
        fecha = _format_date(inv.issue_date or inv.received_date)
        moneda = inv.currency or "PEN"
        subtotal = _format_decimal(inv.subtotal)
        igv = _format_decimal(inv.tax_amount)
        total = _format_decimal(inv.total_amount)
        cdr = inv.cdr_status or "ACCEPTED"

        # Estructura de fila SIRE RCE (Campos mínimos estandarizados)
        row = f"{ruc}|{name}|{doc_type}|{serie}|{corr}|{fecha}|{moneda}|{subtotal}|{igv}|{total}|{cdr}|"
        lines.append(row)

    return "\n".join(lines)


def generate_erp_csv(invoices: Sequence[InvoiceRecord]) -> str:
    """
    Genera un archivo CSV estándar estructurado para importación contable en Concar, Siigo, Starsoft o Excel.
    """
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

    # Encabezados en español técnico contable
    writer.writerow(
        [
            "ID_Mensaje",
            "Fecha_Recepcion",
            "Fecha_Emision",
            "RUC_Emisor",
            "Razon_Social",
            "Tipo_Documento",
            "Serie_Numero",
            "Moneda",
            "Base_Imponible",
            "IGV",
            "Monto_Total",
            "Monto_Detraccion",
            "Estado_CDR",
            "Estado_CajaClara",
        ]
    )

    for inv in invoices:
        writer.writerow(
            [
                inv.message_id,
                _format_date(inv.received_date, "%Y-%m-%d %H:%M"),
                _format_date(inv.issue_date, "%Y-%m-%d"),
                inv.issuer_id or "",
                inv.issuer_name or "",
                inv.document_type or "01",
                inv.invoice_number or "",
                inv.currency or "PEN",
                _format_decimal(inv.subtotal),
                _format_decimal(inv.tax_amount),
                _format_decimal(inv.total_amount),
                _format_decimal(inv.detraction_amount),
                inv.cdr_status or "",
                inv.status,
            ]
        )

    return output.getvalue()
