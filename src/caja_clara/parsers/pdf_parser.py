"""
Extractor cognitivo básico para Facturas en PDF.
Utiliza pdfplumber para extracción de texto crudo y heurísticas regex (preparado para LLM).
"""
import io
import re
from datetime import datetime

import pdfplumber
import structlog
from google import genai

from caja_clara.config import config
from caja_clara.schemas import InvoiceExtraction

logger = structlog.get_logger()

def parse_pdf_invoice(pdf_content: bytes) -> dict:
    """
    Extrae inteligencia cognitiva del PDF. 
    Intenta usar la API de Gemini (Structured Outputs) para devolver un modelo validado.
    Si la API falla o no está configurada, realiza un fallback a heurísticas (RegEx).
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

        # --- Pilar A (Fase 4): Inteligencia Cognitiva Pura (Gemini) ---
        if config.ai_api_key:
            try:
                logger.info("iniciando_extraccion_llm")
                client = genai.Client(api_key=config.ai_api_key)
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=f"Extrae los datos financieros de esta factura. Si no encuentras un dato, déjalo vacío.\n\n{text}",
                    config=genai.types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=InvoiceExtraction,
                        temperature=0.0
                    ),
                )
                
                # Cargar la respuesta tipada del LLM
                import json
                llm_dict = json.loads(response.text)
                
                # Mapear datos (parseando la fecha si aplica)
                for k in result:
                    if k == "issue_date" and llm_dict.get(k):
                        try:
                            result[k] = datetime.strptime(llm_dict[k], "%Y-%m-%d")
                        except ValueError:
                            pass
                    else:
                        if llm_dict.get(k) is not None:
                            result[k] = llm_dict.get(k)
                            
                logger.info("extraccion_llm_exitosa", invoice_number=result.get("invoice_number"))
                return result # Salir exitosamente
                
            except Exception as e:
                logger.warning("fallo_extraccion_llm_usando_fallback", error=str(e))
                
        # --- Fallback: Lógica heurística (RegEx) ---
        logger.debug("usando_heuristica_regex_pdf")
        
        ruc_match = re.search(r"(?:RUC|NIT)[:\s]*([0-9]{10,13})", text, re.IGNORECASE)
        if ruc_match:
            result["issuer_id"] = ruc_match.group(1)
            
        inv_match = re.search(r"(?:Factura|FV|FC)[\sNºN°:]*([FBE0-9]{3,4}-[0-9]{4,8})", text, re.IGNORECASE)
        if inv_match:
            result["invoice_number"] = inv_match.group(1)
            
        total_match = re.search(r"(?:Total|Monto Total)[\sS/$\.:]*([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2})", text, re.IGNORECASE)
        if total_match:
            try:
                clean_total = total_match.group(1).replace(",", "")
                result["total_amount"] = float(clean_total)
            except ValueError:
                pass
                
        date_match = re.search(r"(?:Fecha|Emisión)[:\s]*([0-9]{2}/[0-9]{2}/[0-9]{4})", text, re.IGNORECASE)
        if date_match:
            try:
                result["issue_date"] = datetime.strptime(date_match.group(1), "%d/%m/%Y")
            except ValueError:
                pass

        logger.info("pdf_procesado_heuristicamente", invoice_number=result.get("invoice_number"))
        
    except Exception as e:
        logger.warning("error_parseando_pdf", error=str(e))
        
    return result
