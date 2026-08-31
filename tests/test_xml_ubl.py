import io
import zipfile
from decimal import Decimal

from caja_clara.extractor import _process_zip_payload
from caja_clara.parsers.xml_parser import parse_cdr_xml, parse_xml_invoice

SAMPLE_UBL_INVOICE = b"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
    <cbc:ID>F001-00045678</cbc:ID>
    <cbc:IssueDate>2026-08-15</cbc:IssueDate>
    <cbc:InvoiceTypeCode>01</cbc:InvoiceTypeCode>
    <cbc:DocumentCurrencyCode>PEN</cbc:DocumentCurrencyCode>
    <cac:AccountingSupplierParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID schemeID="6">20601234567</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName>SERVICIOS CLOUD PERU S.A.C.</cbc:RegistrationName>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:TaxTotal>
        <cbc:TaxAmount currencyID="PEN">180.00</cbc:TaxAmount>
    </cac:TaxTotal>
    <cac:LegalMonetaryTotal>
        <cbc:LineExtensionAmount currencyID="PEN">1000.00</cbc:LineExtensionAmount>
        <cbc:PayableAmount currencyID="PEN">1180.00</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>
    <cac:PaymentTerms>
        <cbc:ID>Detraccion</cbc:ID>
        <cbc:PaymentMeansID>001</cbc:PaymentMeansID>
        <cbc:PaymentPercent>12.00</cbc:PaymentPercent>
        <cbc:Amount currencyID="PEN">141.60</cbc:Amount>
    </cac:PaymentTerms>
</Invoice>
"""

SAMPLE_UBL_CREDIT_NOTE = b"""<?xml version="1.0" encoding="UTF-8"?>
<CreditNote xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
            xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
            xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
    <cbc:ID>FC01-0000012</cbc:ID>
    <cbc:IssueDate>2026-08-20</cbc:IssueDate>
    <cbc:DocumentCurrencyCode>USD</cbc:DocumentCurrencyCode>
    <cac:AccountingSupplierParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID>20509876543</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name>PROVEEDOR INTERNACIONAL S.A.</cbc:Name>
            </cac:PartyName>
        </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:TaxTotal>
        <cbc:TaxAmount currencyID="USD">18.00</cbc:TaxAmount>
    </cac:TaxTotal>
    <cac:LegalMonetaryTotal>
        <cbc:LineExtensionAmount currencyID="USD">100.00</cbc:LineExtensionAmount>
        <cbc:PayableAmount currencyID="USD">118.00</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>
</CreditNote>
"""

SAMPLE_CDR_ACCEPTED = b"""<?xml version="1.0" encoding="UTF-8"?>
<ApplicationResponse xmlns="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2"
                     xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
                     xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
    <cac:DocumentResponse>
        <cac:Response>
            <cbc:ResponseCode>0</cbc:ResponseCode>
            <cbc:Description>La Factura numero F001-00045678, ha sido aceptada</cbc:Description>
        </cac:Response>
    </cac:DocumentResponse>
</ApplicationResponse>
"""

SAMPLE_CDR_REJECTED = b"""<?xml version="1.0" encoding="UTF-8"?>
<ApplicationResponse xmlns="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2"
                     xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
                     xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
    <cac:DocumentResponse>
        <cac:Response>
            <cbc:ResponseCode>2324</cbc:ResponseCode>
            <cbc:Description>El RUC del emisor no se encuentra activo</cbc:Description>
        </cac:Response>
    </cac:DocumentResponse>
</ApplicationResponse>
"""

XXE_MALICIOUS_PAYLOAD = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE root [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
    <cbc:ID>&xxe;</cbc:ID>
    <cbc:IssueDate>2026-08-01</cbc:IssueDate>
</Invoice>
"""


def test_parse_xml_invoice_ubl():
    """Valida la extracción determinista de campos clave de una factura UBL 2.1."""
    data = parse_xml_invoice(SAMPLE_UBL_INVOICE)

    assert data["invoice_number"] == "F001-00045678"
    assert data["document_type"] == "01"
    assert data["issuer_id"] == "20601234567"
    assert data["issuer_name"] == "SERVICIOS CLOUD PERU S.A.C."
    assert data["currency"] == "PEN"
    assert data["subtotal"] == Decimal("1000.00")
    assert data["tax_amount"] == Decimal("180.00")
    assert data["total_amount"] == Decimal("1180.00")
    assert data["detraction_amount"] == Decimal("141.60")
    assert data["detraction_rate"] == Decimal("12.00")
    assert data["issue_date"] is not None
    assert data["issue_date"].strftime("%Y-%m-%d") == "2026-08-15"


def test_parse_xml_credit_note():
    """Valida que una Nota de Crédito UBL 2.1 se clasifique como document_type '07'."""
    data = parse_xml_invoice(SAMPLE_UBL_CREDIT_NOTE)

    assert data["invoice_number"] == "FC01-0000012"
    assert data["document_type"] == "07"
    assert data["issuer_id"] == "20509876543"
    assert data["issuer_name"] == "PROVEEDOR INTERNACIONAL S.A."
    assert data["currency"] == "USD"
    assert data["total_amount"] == Decimal("118.00")


def test_parse_cdr_xml_statuses():
    """Valida la detección de estado de aceptación o rechazo en Constancias de Recepción (CDR)."""
    ok_res = parse_cdr_xml(SAMPLE_CDR_ACCEPTED)
    assert ok_res["status"] == "ACCEPTED"
    assert ok_res["response_code"] == "0"
    assert "ha sido aceptada" in ok_res["description"]

    rej_res = parse_cdr_xml(SAMPLE_CDR_REJECTED)
    assert rej_res["status"] == "REJECTED"
    assert rej_res["response_code"] == "2324"


def test_process_zip_with_xml_and_cdr():
    """Valida la descompresión en memoria de un archivo ZIP conteniendo XML + CDR."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("20601234567-01-F001-00045678.xml", SAMPLE_UBL_INVOICE)
        z.writestr("R-20601234567-01-F001-00045678.xml", SAMPLE_CDR_ACCEPTED)

    zip_payload = zip_buffer.getvalue()
    data, err = _process_zip_payload(zip_payload)

    assert err is None
    assert data["invoice_number"] == "F001-00045678"
    assert data["issuer_id"] == "20601234567"
    assert data["total_amount"] == Decimal("1180.00")
    assert data["cdr_status"] == "ACCEPTED"


def test_process_zip_bad_archive():
    """Valida que un ZIP corrupto retorne error sin provocar excepciones."""
    data, err = _process_zip_payload(b"not_a_real_zip_file_content")
    assert err is not None
    assert "ZIP corrupto" in err
    assert data == {}


def test_xxe_protection_in_xml_parser():
    """Valida que el parser seguro de XML no resuelva entidades externas maliciosas (XXE)."""
    data = parse_xml_invoice(XXE_MALICIOUS_PAYLOAD)
    # Debe retornar sin explotar y sin inyectar contenido de /etc/passwd
    assert data["invoice_number"] != "/etc/passwd"
    assert data["invoice_number"] == "" or data["invoice_number"] is None
