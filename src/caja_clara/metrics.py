"""
Módulo de observabilidad y métricas para Prometheus / OpenMetrics.
"""

from prometheus_client import REGISTRY, CollectorRegistry, Counter, Gauge, Histogram

# Métricas estándar de CajaClara
INVOICES_TOTAL = Counter(
    "cajaclara_invoices_total",
    "Total de comprobantes fiscales procesados por CajaClara",
    ["status", "document_type", "currency"],
)

MAILBOX_INVOICES_TOTAL = Counter(
    "cajaclara_mailbox_invoices_total",
    "Total de comprobantes procesados por buzón, estado, tipo y moneda",
    ["mailbox", "status", "document_type", "currency"],
)

PROCESSING_DURATION_SECONDS = Histogram(
    "cajaclara_processing_duration_seconds",
    "Duración de procesamiento y extracción de comprobantes en segundos",
    ["parser", "status"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

IMAP_CONNECTION_STATUS = Gauge(
    "cajaclara_imap_connection_status",
    "Estado actual de la conexión IMAP global (1 = conectado, 0 = desconectado)",
)

MAILBOX_STATUS = Gauge(
    "cajaclara_mailbox_status",
    "Estado actual de la conexión por buzón IMAP (1 = conectado, 0 = desconectado/error)",
    ["mailbox"],
)

RESIDENT_MEMORY_BYTES = Gauge(
    "cajaclara_resident_memory_bytes",
    "Memoria física residente (RSS) del proceso en bytes",
)

DB_SIZE_BYTES = Gauge(
    "cajaclara_db_size_bytes",
    "Tamaño en bytes del archivo SQLite local",
)

OUTBOX_QUEUE_DEPTH = Gauge(
    "cajaclara_outbox_queue_depth",
    "Cantidad de eventos outbox encolados por estado",
    ["status"],
)

OUTBOX_DELIVERY_DURATION_SECONDS = Histogram(
    "cajaclara_outbox_delivery_duration_seconds",
    "Latencia de entrega de eventos outbox hacia endpoints externos en segundos",
    ["event_type", "status"],
    buckets=[0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

OUTBOX_DELIVERY_RETRIES_TOTAL = Counter(
    "cajaclara_outbox_retries_total",
    "Total de reintentos de despacho de eventos outbox",
    ["event_type"],
)

OUTBOX_EVENTS_TOTAL = Counter(
    "cajaclara_outbox_events_total",
    "Total acumulado de eventos outbox despachados por estado final",
    ["event_type", "status"],
)

FISCAL_ALERTS_TOTAL = Counter(
    "cajaclara_fiscal_alerts_total",
    "Total de anomalías y alertas fiscales detectadas durante la extracción",
    ["alert_type", "severity"],
)

# Métricas de Replicación Continua y Disaster Recovery (Litestream / S3)
LITESTREAM_LAG_SECONDS = Gauge(
    "cajaclara_litestream_lag_seconds",
    "Latencia de replicación entre SQLite local y almacenamiento S3/R2 en segundos",
    ["replica", "storage_provider"],
)

REPLICATION_STATUS = Gauge(
    "cajaclara_replication_status",
    "Estado de la réplica continua (1 = sincronizando/activo, 0 = degradado/desconectado)",
    ["replica", "storage_provider"],
)

LAST_SNAPSHOT_TIMESTAMP = Gauge(
    "cajaclara_last_snapshot_timestamp",
    "Timestamp Unix (segundos desde epoch) de la última instantánea completa en S3/R2",
    ["replica", "storage_provider"],
)

REPLICATION_SYNC_ERRORS_TOTAL = Counter(
    "cajaclara_replication_sync_errors_total",
    "Total acumulado de fallos de red o errores HTTP al sincronizar frames WAL a S3/R2",
    ["replica", "error_type"],
)


def get_metrics_registry() -> CollectorRegistry:
    """Retorna el registro global de métricas de Prometheus."""
    return REGISTRY
