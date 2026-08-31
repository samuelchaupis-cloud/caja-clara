from prometheus_client import generate_latest

from caja_clara.metrics import (
    DB_SIZE_BYTES,
    IMAP_CONNECTION_STATUS,
    INVOICES_TOTAL,
    OUTBOX_QUEUE_DEPTH,
    PROCESSING_DURATION_SECONDS,
    get_metrics_registry,
)


def test_metrics_initialization_and_scrape():
    """Valida la inicialización de métricas Prometheus y emisión de texto OpenMetrics."""
    registry = get_metrics_registry()

    # Manipular métricas para simular actividad
    INVOICES_TOTAL.labels(status="PROCESSED", document_type="01", currency="PEN").inc()
    PROCESSING_DURATION_SECONDS.labels(parser="xml_ubl", status="success").observe(0.012)
    IMAP_CONNECTION_STATUS.set(1)
    DB_SIZE_BYTES.set(20480)
    OUTBOX_QUEUE_DEPTH.labels(status="PENDING").set(3)

    output = generate_latest(registry).decode("utf-8")

    assert "cajaclara_invoices_total" in output
    assert "cajaclara_processing_duration_seconds" in output
    assert "cajaclara_imap_connection_status 1.0" in output
    assert "cajaclara_db_size_bytes 20480.0" in output
    assert "cajaclara_outbox_queue_depth" in output
