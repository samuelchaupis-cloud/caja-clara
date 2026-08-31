import io
from decimal import Decimal
from unittest.mock import MagicMock, patch

from pypdf import PageObject, PdfWriter

from caja_clara.parsers.pdf_parser import parse_pdf_invoice


def _create_sample_pdf(text_content: str, pages_count: int = 1) -> bytes:
    """Genera un archivo PDF sintético en memoria con texto."""
    writer = PdfWriter()
    for _ in range(pages_count):
        # Crear una página básica en blanco
        page = PageObject.create_blank_page(width=612, height=792)
        writer.add_page(page)

    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_parse_pdf_invoice_regex_fallback():
    """Valida la extracción por heurísticas regex sobre texto de PDF."""
    sample_text = "FACTURA ELECTRONICA\nRUC: 20456789012\nFactura Nº F001-0009988\nFecha de Emisión: 15/08/2026\nMonto Total: S/ 1,250.50\n"

    with patch("pdfplumber.open") as mock_open:
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = sample_text
        mock_pdf.pages = [mock_page]
        mock_open.return_value.__enter__.return_value = mock_pdf

        data = parse_pdf_invoice(b"dummy_pdf_bytes")
        assert data["issuer_id"] == "20456789012"
        assert data["invoice_number"] == "F001-0009988"
        assert data["total_amount"] == Decimal("1250.50")
        assert data["issue_date"] is not None


def test_parse_pdf_invoice_pdf_bomb_protection():
    """Valida que un PDF con más de 20 páginas sea rechazado por protección contra DoS."""
    with patch("pdfplumber.open") as mock_open:
        mock_pdf = MagicMock()
        mock_pdf.pages = [MagicMock() for _ in range(25)]
        mock_open.return_value.__enter__.return_value = mock_pdf

        data = parse_pdf_invoice(b"large_pdf_bytes")
        assert data["invoice_number"] is None
        assert data["total_amount"] is None


def test_parse_pdf_invoice_llm_flow():
    """Valida el flujo con Gemini Structured Outputs cuando AI_API_KEY está configurada."""
    with patch("caja_clara.parsers.pdf_parser.config") as mock_config:
        mock_config.ai_api_key = "fake_gemini_key"

        with patch("pdfplumber.open") as mock_open:
            mock_pdf = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Factura de Consultoría"
            mock_pdf.pages = [mock_page]
            mock_open.return_value.__enter__.return_value = mock_pdf

            with patch("google.genai.Client") as mock_client_cls:
                mock_client = mock_client_cls.return_value
                mock_response = MagicMock()
                mock_response.text = (
                    '{"issuer_id": "20111222333", "issuer_name": "AI CORP", '
                    '"invoice_number": "F100-1", "issue_date": "2026-08-30", '
                    '"currency": "USD", "subtotal": 100.0, "tax_amount": 18.0, "total_amount": 118.0}'
                )
                mock_client.models.generate_content.return_value = mock_response

                data = parse_pdf_invoice(b"dummy_bytes")
                assert data["issuer_id"] == "20111222333"
                assert data["issuer_name"] == "AI CORP"
                assert data["invoice_number"] == "F100-1"
                assert data["currency"] == "USD"
