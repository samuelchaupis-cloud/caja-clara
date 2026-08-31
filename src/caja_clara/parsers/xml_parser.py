"""
Extractor de datos estructurados para Facturas Electrónicas XML (UBL 2.1 estándar y CDR SUNAT).
Implementa un parser determinista seguro contra vulnerabilidades XXE y con soporte de namespaces.
"""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import structlog
from lxml import etree

logger = structlog.get_logger()

# Configuración de parser seguro contra XXE (XML External Entity Injection) y DoS
SAFE_XML_PARSER = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    dtd_validation=False,
    load_dtd=False,
    huge_tree=False,
)


def _extract_doc_type(root: etree._Element) -> str:
    tag_name = root.tag.split("}")[-1] if "}" in root.tag else root.tag
    if tag_name == "CreditNote":
        return "07"
    if tag_name == "DebitNote":
        return "08"
    type_nodes = root.xpath('//*[local-name()="InvoiceTypeCode"]/text()')
    return str(type_nodes[0]).strip() if type_nodes else "01"


def _extract_invoice_number(root: etree._Element) -> str | None:
    id_nodes = root.xpath('/*/*[local-name()="ID"]/text() | /*[local-name()="ID"]/text()')
    if id_nodes:
        return str(id_nodes[0]).strip()
    any_id = root.xpath('//*[local-name()="ID"]/text()')
    return str(any_id[0]).strip() if any_id else None


def _extract_supplier_info(root: etree._Element) -> tuple[str | None, str | None]:
    issuer_id = None
    issuer_name = None
    supplier_nodes = root.xpath('//*[local-name()="AccountingSupplierParty"]')
    if supplier_nodes:
        supplier = supplier_nodes[0]
        ruc_nodes = supplier.xpath(
            './/*[local-name()="CustomerAssignedAccountID"]/text() | .//*[local-name()="CompanyID"]/text() | .//*[local-name()="ID"]/text()'
        )
        if ruc_nodes:
            issuer_id = str(ruc_nodes[0]).strip()

        name_nodes = supplier.xpath('.//*[local-name()="RegistrationName"]/text() | .//*[local-name()="PartyName"]/*[local-name()="Name"]/text()')
        if name_nodes:
            issuer_name = str(name_nodes[0]).strip()
    return issuer_id, issuer_name


def _extract_issue_date(root: etree._Element) -> datetime | None:
    date_nodes = root.xpath('//*[local-name()="IssueDate"]/text()')
    if date_nodes:
        date_str = str(date_nodes[0]).strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
            try:
                return datetime.strptime(date_str, fmt).replace(tzinfo=UTC)
            except ValueError:
                pass
    return None


def _extract_monetary_amounts(
    root: etree._Element,
) -> tuple[Decimal | None, Decimal | None, Decimal | None, Decimal | None, Decimal | None]:
    subtotal = None
    tax_amount = None
    total_amount = None
    detraction_amount = None
    detraction_rate = None

    # Total
    total_xpath = (
        '//*[local-name()="LegalMonetaryTotal"]/*[local-name()="PayableAmount"]/text() | '
        '//*[local-name()="RequestedMonetaryTotal"]/*[local-name()="PayableAmount"]/text()'
    )
    total_nodes = root.xpath(total_xpath)
    if total_nodes:
        try:
            total_amount = Decimal(str(total_nodes[0]).strip())
        except (InvalidOperation, ValueError, TypeError):
            pass

    # Subtotal
    subtotal_xpath = (
        '//*[local-name()="LegalMonetaryTotal"]/*[local-name()="LineExtensionAmount"]/text() | '
        '//*[local-name()="RequestedMonetaryTotal"]/*[local-name()="LineExtensionAmount"]/text()'
    )
    subtotal_nodes = root.xpath(subtotal_xpath)
    if subtotal_nodes:
        try:
            subtotal = Decimal(str(subtotal_nodes[0]).strip())
        except (InvalidOperation, ValueError, TypeError):
            pass

    # Impuestos
    tax_nodes = root.xpath('//*[local-name()="TaxTotal"]/*[local-name()="TaxAmount"]/text()')
    if tax_nodes:
        try:
            tax_amount = Decimal(str(tax_nodes[0]).strip())
        except (InvalidOperation, ValueError, TypeError):
            pass

    # Detracciones SPOT SUNAT
    detr_terms = root.xpath(
        '//*[local-name()="PaymentTerms"][normalize-space(*[local-name()="ID"]/text())="Detraccion" or '
        'normalize-space(*[local-name()="PaymentMeansID"]/text())="001" or '
        'contains(*[local-name()="ID"]/text(), "Detrac") or '
        'contains(*[local-name()="PaymentMeansID"]/text(), "Detrac")]'
    )
    if detr_terms:
        term = detr_terms[0]
        amt_nodes = term.xpath('.//*[local-name()="Amount"]/text()')
        if amt_nodes:
            try:
                detraction_amount = Decimal(str(amt_nodes[0]).strip())
            except (InvalidOperation, ValueError, TypeError):
                pass

        pct_nodes = term.xpath('.//*[local-name()="PaymentPercent"]/text()')
        if pct_nodes:
            try:
                detraction_rate = Decimal(str(pct_nodes[0]).strip())
            except (InvalidOperation, ValueError, TypeError):
                pass
    else:
        # Fallback: sólo si no hay cuotas de crédito registradas
        has_credit_installments = bool(root.xpath('//*[local-name()="PaymentTerms"][contains(*[local-name()="ID"]/text(), "Cuota")]'))
        if not has_credit_installments:
            detr_amt_nodes = root.xpath('//*[local-name()="PaymentTerms"]/*[local-name()="Amount"]/text()')
            if detr_amt_nodes:
                try:
                    detraction_amount = Decimal(str(detr_amt_nodes[0]).strip())
                except (InvalidOperation, ValueError, TypeError):
                    pass

    return subtotal, tax_amount, total_amount, detraction_amount, detraction_rate


def parse_xml_invoice(xml_content: bytes) -> dict[str, Any]:
    """
    Parsea deterministamente un comprobante electrónico XML (UBL 2.1)
    extrayendo metadatos fiscales, montos en Decimal e identificadores.
    """
    result: dict[str, Any] = {
        "document_type": "01",
        "issuer_id": None,
        "issuer_name": None,
        "invoice_number": None,
        "issue_date": None,
        "currency": "PEN",
        "subtotal": None,
        "tax_amount": None,
        "total_amount": None,
        "detraction_amount": None,
        "detraction_rate": None,
        "cdr_status": None,
        "reference_document_type": None,
        "reference_invoice_number": None,
        "discrepancy_code": None,
        "discrepancy_reason": None,
    }

    try:
        root = etree.fromstring(xml_content, parser=SAFE_XML_PARSER)

        result["document_type"] = _extract_doc_type(root)
        result["invoice_number"] = _extract_invoice_number(root)
        result["issuer_id"], result["issuer_name"] = _extract_supplier_info(root)
        result["issue_date"] = _extract_issue_date(root)

        curr_nodes = root.xpath('//*[local-name()="DocumentCurrencyCode"]/text()')
        if curr_nodes:
            result["currency"] = str(curr_nodes[0]).strip()

        (
            result["subtotal"],
            result["tax_amount"],
            result["total_amount"],
            result["detraction_amount"],
            result["detraction_rate"],
        ) = _extract_monetary_amounts(root)

        # Referencias de Notas de Crédito / Débito (UBL 2.1)
        ref_id_nodes = root.xpath('//*[local-name()="BillingReference"]/*[local-name()="InvoiceDocumentReference"]/*[local-name()="ID"]/text()')
        if ref_id_nodes:
            result["reference_invoice_number"] = str(ref_id_nodes[0]).strip()

        ref_type_nodes = root.xpath(
            '//*[local-name()="BillingReference"]/*[local-name()="InvoiceDocumentReference"]/*[local-name()="DocumentTypeCode"]/text()'
        )
        if ref_type_nodes:
            result["reference_document_type"] = str(ref_type_nodes[0]).strip()

        disc_code_nodes = root.xpath('//*[local-name()="DiscrepancyResponse"]/*[local-name()="ResponseCode"]/text()')
        if disc_code_nodes:
            result["discrepancy_code"] = str(disc_code_nodes[0]).strip()

        disc_desc_nodes = root.xpath('//*[local-name()="DiscrepancyResponse"]/*[local-name()="Description"]/text()')
        if disc_desc_nodes:
            result["discrepancy_reason"] = str(disc_desc_nodes[0]).strip()

        logger.info(
            "xml_ubl_procesado_exitosamente",
            invoice_number=result["invoice_number"],
            doc_type=result["document_type"],
            total=str(result["total_amount"]),
        )

    except Exception as e:
        logger.warning("error_parseando_xml_ubl", error=str(e))

    return result


def parse_cdr_xml(xml_content: bytes) -> dict[str, Any]:
    """
    Parsea una Constancia de Recepción (CDR) oficial de SUNAT (R-*.xml).
    Valida si el comprobante fue aceptado (ResponseCode == '0').
    """
    result = {
        "status": "UNKNOWN",
        "response_code": None,
        "description": None,
    }
    try:
        root = etree.fromstring(xml_content, parser=SAFE_XML_PARSER)
        code_nodes = root.xpath('//*[local-name()="ResponseCode"]/text()')
        desc_nodes = root.xpath('//*[local-name()="Description"]/text()')

        if code_nodes:
            result["response_code"] = str(code_nodes[0]).strip()
            result["status"] = "ACCEPTED" if result["response_code"] == "0" else "REJECTED"

        if desc_nodes:
            result["description"] = str(desc_nodes[0]).strip()

        logger.info("cdr_procesado", status=result["status"], code=result["response_code"])
    except Exception as e:
        logger.warning("error_parseando_cdr", error=str(e))

    return result
