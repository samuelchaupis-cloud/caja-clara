"""
Extractor de datos estructurados para Facturas Electrónicas XML (UBL estándar).
"""
import structlog
from lxml import etree
from datetime import datetime

logger = structlog.get_logger()

def parse_xml_invoice(xml_content: bytes) -> dict:
    """
    Parsea el XML (UBL) e intenta extraer montos, RUC y fechas usando heurísticas.
    Retorna un diccionario con los datos financieros encontrados.
    """
    result = {
        "issuer_id": None,
        "issuer_name": None,
        "invoice_number": None,
        "issue_date": None,
        "currency": None,
        "subtotal": None,
        "tax_amount": None,
        "total_amount": None,
    }
    
    try:
        # Recuperación de namespace genérica ignorándolos al buscar (lxml soporta XPath con local-name())
        root = etree.fromstring(xml_content)
        
        # Heurísticas de búsqueda UBL
        
        # 1. Invoice Number (Folio/Serie)
        invoice_id_node = root.xpath('//*[local-name()="ID"]/text()')
        if invoice_id_node:
            # Tomamos el primero que suele ser el ID del documento
            result["invoice_number"] = str(invoice_id_node[0]).strip()
            
        # 2. Issuer ID (RUC/NIT)
        issuer_nodes = root.xpath('//*[local-name()="AccountingSupplierParty"]//*[local-name()="ID"]/text()')
        if issuer_nodes:
            result["issuer_id"] = str(issuer_nodes[0]).strip()
            
        # 3. Issuer Name
        issuer_name_nodes = root.xpath('//*[local-name()="AccountingSupplierParty"]//*[local-name()="RegistrationName"]/text()')
        if issuer_name_nodes:
            result["issuer_name"] = str(issuer_name_nodes[0]).strip()
            
        # 4. Issue Date
        date_nodes = root.xpath('//*[local-name()="IssueDate"]/text()')
        if date_nodes:
            try:
                result["issue_date"] = datetime.strptime(str(date_nodes[0]).strip(), "%Y-%m-%d")
            except ValueError:
                pass # Formato inesperado
                
        # 5. Currency
        currency_nodes = root.xpath('//*[local-name()="DocumentCurrencyCode"]/text()')
        if currency_nodes:
            result["currency"] = str(currency_nodes[0]).strip()
            
        # 6. Total Amount
        total_nodes = root.xpath('//*[local-name()="LegalMonetaryTotal"]//*[local-name()="PayableAmount"]/text()')
        if total_nodes:
            try:
                result["total_amount"] = float(str(total_nodes[0]).strip())
            except ValueError:
                pass
                
        # 7. Subtotal y Taxes
        subtotal_nodes = root.xpath('//*[local-name()="LegalMonetaryTotal"]//*[local-name()="LineExtensionAmount"]/text()')
        if subtotal_nodes:
            try:
                result["subtotal"] = float(str(subtotal_nodes[0]).strip())
            except ValueError:
                pass
                
        tax_nodes = root.xpath('//*[local-name()="TaxTotal"]//*[local-name()="TaxAmount"]/text()')
        if tax_nodes:
            try:
                result["tax_amount"] = float(str(tax_nodes[0]).strip())
            except ValueError:
                pass

        logger.info("xml_procesado_exitosamente", invoice_number=result["invoice_number"])
        
    except Exception as e:
        logger.warning("error_parseando_xml", error=str(e))
        
    return result
