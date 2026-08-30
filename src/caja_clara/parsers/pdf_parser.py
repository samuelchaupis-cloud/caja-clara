"""
Extractor cognitivo básico para Facturas en PDF.
Utiliza pdfplumber para extracción de texto crudo y heurísticas regex (preparado para LLM).
"""
import io
import re
import structlog
from datetime import datetime
import pdfplumber

logger = structlog.get_logger()

def parse_pdf_invoice(pdf_content: bytes) -> dict:
    """
    Abre el PDF con pdfplumber, extrae el texto y busca patrones de facturación.
    Esta función está diseñada para ser reemplazada/aumentada con *Function Calling* de LLMs (OpenAI/Gemini).
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
        text = ""
        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
                    
        # --- Lógica heurística (Fallback cognitivo si no hay LLM) ---
        
        # RUC (Patrón genérico: palabra RUC/NIT seguida de números)
        ruc_match = re.search(r"(?:RUC|NIT)[:\s]*([0-9]{10,13})", text, re.IGNORECASE)
        if ruc_match:
            result["issuer_id"] = ruc_match.group(1)
            
        # Factura (Patrón: F001-000123)
        inv_match = re.search(r"(?:Factura|FV|FC)[\sNºN°:]*([FBE0-9]{3,4}-[0-9]{4,8})", text, re.IGNORECASE)
        if inv_match:
            result["invoice_number"] = inv_match.group(1)
            
        # Total (Patrón: Total: 1,500.00)
        total_match = re.search(r"(?:Total|Monto Total)[\sS/$\.:]*([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2})", text, re.IGNORECASE)
        if total_match:
            # Limpiar comas para casting a float
            try:
                clean_total = total_match.group(1).replace(",", "")
                result["total_amount"] = float(clean_total)
            except ValueError:
                pass
                
        # Fecha (Patrón: DD/MM/YYYY)
        date_match = re.search(r"(?:Fecha|Emisión)[:\s]*([0-9]{2}/[0-9]{2}/[0-9]{4})", text, re.IGNORECASE)
        if date_match:
            try:
                result["issue_date"] = datetime.strptime(date_match.group(1), "%d/%m/%Y")
            except ValueError:
                pass

        logger.info("pdf_procesado_heuristicamente", invoice_number=result["invoice_number"])
        
    except Exception as e:
        logger.warning("error_parseando_pdf", error=str(e))
        
    return result
