import io
import tracemalloc
import zipfile

from caja_clara.constants import MAX_ATTACHMENT_SIZE_BYTES
from caja_clara.extractor import _process_zip_payload, extract_email_data
from caja_clara.metrics import RESIDENT_MEMORY_BYTES
from tests.test_mailbox_pool import DummyAttachment, DummyMailMessage


def test_memory_saturation_streaming():
    """Valida que el procesamiento en streaming de 1,000 correos en memoria no exceda los 35MB."""
    tracemalloc.start()

    sample_xml = b"""<?xml version="1.0" encoding="ISO-8859-1"?>
    <Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">
        <ID>F001-00099999</ID>
        <IssueDate>2026-08-31</IssueDate>
        <DocumentCurrencyCode>PEN</DocumentCurrencyCode>
        <LegalMonetaryTotal><PayableAmount>500.00</PayableAmount></LegalMonetaryTotal>
    </Invoice>"""

    for i in range(1000):
        msg = DummyMailMessage(
            uid=str(i),
            from_="proveedor@empresa.com",
            subject=f"Factura #{i}",
            attachments=[DummyAttachment(f"invoice_{i}.xml", sample_xml)],
        )
        extract, err = extract_email_data(msg, "facturas@empresa.com")
        assert err is None
        assert extract is not None

    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Invariante de Memoria: El pico no debe superar 35MB (bien por debajo del cgroup 45MB)
    assert peak < 35 * 1024 * 1024, f"Pico de memoria excesivo: {peak / (1024 * 1024):.2f} MB"


def test_zip_stream_quota_enforcement():
    """Valida que un ZIP descomprimido que exceda 10MB sea cortado en streaming antes de colapsar la RAM."""
    # Construir un ZIP con un fichero grande (> 10MB)
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # 11MB de ceros (muy comprimible en bytes, pero expande > 10MB)
        z.writestr("huge_invoice.xml", b"0" * (11 * 1024 * 1024))

    zip_bytes = zip_buf.getvalue()
    parsed_data, err = _process_zip_payload(zip_bytes)

    assert err is not None
    assert "excede el límite de 10MB" in err
    assert parsed_data == {}


def test_max_attachment_size_constant():
    """Valida que MAX_ATTACHMENT_SIZE_BYTES sea 8MB para compatibilidad con cgroups 45MB."""
    assert MAX_ATTACHMENT_SIZE_BYTES == 8 * 1024 * 1024


def test_resident_memory_gauge():
    """Valida que la métrica RESIDENT_MEMORY_BYTES registre valores numéricos positivos."""
    RESIDENT_MEMORY_BYTES.set(25 * 1024 * 1024)
    # Scraping
    val = RESIDENT_MEMORY_BYTES._value.get()
    assert val == 25 * 1024 * 1024
