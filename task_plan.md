# Task Plan: CajaClara — Plataforma Fiscal y Concurrencia Enterprise

**Estado General:** Fases 7, 8 y 9 completadas al 100% (71 tests en verde, 85.49% de cobertura real sin mocks).

---

## Fases del Proyecto

### ✅ Fase 7: Motor Fiscal UBL 2.1, Descompresión ZIP & Exportador Contable (COMPLETADA)
- [x] Agregar `".zip"` a `ALLOWED_ATTACHMENT_EXTENSIONS` en `constants.py`.
- [x] Actualizar `schemas.py` (`InvoiceExtraction`, `EmailExtract`) con campos fiscales y soporte para `Decimal`.
- [x] Actualizar `models.py` (`InvoiceRecord`) con campos `document_type`, `detraction_amount`, `detraction_rate` y tipos `Numeric(12, 2)`.
- [x] Reescribir `src/caja_clara/parsers/xml_parser.py` con soporte UBL 2.1 (Facturas, Boletas, NC, ND, CDRs SUNAT y protección XXE).
- [x] Actualizar `src/caja_clara/extractor.py` con descompresión segura en memoria de `.zip` y prioridad XML > ZIP > PDF.
- [x] Crear `src/caja_clara/reports.py` con generadores de SIRE RCE (SUNAT) y CSV para ERPs.
- [x] Agregar endpoints `/api/v1/reports/sire`, `/api/v1/reports/export`, `/health/live` y `/health/ready` en `api.py`.
- [x] Dashboard enriquecido con badges fiscales y enlaces de descarga en `dashboard.html`.
- [x] Saneamiento integral de pruebas sin mocks de BD (`tests/test_main.py`, `tests/test_xml_ubl.py`, `tests/test_reports.py`, `tests/test_cli_monitor.py`, `tests/test_pdf_parser.py`, `tests/test_logging.py`).
- [x] Quality Gates aprobados (`ruff` 0 errores, `bandit` 0 vulnerabilidades, `pytest` 56/56 tests, 85.68% de cobertura).

---

### ✅ Fase 8: Hardening de Concurrencia, Observabilidad Prometheus & Transactional Outbox (COMPLETADA)
- [x] **Detracciones SPOT Precisas:** Refinar selector XPath en `xml_parser.py` para aislar `PaymentTerms` de detracción (`cbc:ID = 'Detraccion'`) y extraer porcentaje `PaymentPercent` (eliminando falsos positivos con cuotas a crédito).
- [x] **Concurrencia SQLite `BEGIN IMMEDIATE`:** Configurar listener en `database.py` para forzar `BEGIN IMMEDIATE` en escrituras y erradicar deadlocks `SQLITE_BUSY` (Protocolo 4.2).
- [x] **Índices de Rendimiento:** Añadir `index=True` a la columna `attachment_hash` en `models.py`.
- [x] **Aislamiento y Timeout LLM:** Incorporar timeout explícito en la llamada de Gemini en `pdf_parser.py`.
- [x] **Contención de Memoria Systemd:** Añadir `MemoryMax=45M` y `MemoryHigh=40M` en `deploy/cajaclarad.service`.
- [x] **Módulo de Métricas:** Crear `src/caja_clara/metrics.py` e integrar `prometheus-client` (`cajaclara_invoices_total`, latencias, estado IMAP).
- [x] **Endpoint `/metrics`:** Exponer `/metrics` en `api.py` con formato OpenMetrics.
- [x] **Hardening PII:** Actualizar `redact_pii` en `logging_config.py` para ofuscar universalmente RUCs/emails sin bypass de DEBUG.
- [x] **Configuración Litestream:** Crear `deploy/litestream.yml` para streaming continuo de SQLite WAL a Cloudflare R2 / S3.
- [x] **Modelo y Tabla Outbox:** Añadir `OutboxEvent` en `models.py` y `schemas.py`.
- [x] **Persistencia Atómica:** Registrar eventos outbox en la misma transacción (`BEGIN IMMEDIATE`) de `InvoiceRecord` en `main.py`.
- [x] **Firma HMAC-SHA256:** Crear helper criptográfico para firmas `X-CajaClara-Signature` con timestamp anti-replay.
- [x] **Suite de Pruebas y Quality Gates:** Cobertura $\ge 85\%$ con tests para métricas, outbox y detracciones en SQLite `:memory:`.

---

### ✅ Fase 9: Outbox Dispatcher Asíncrono, Alertas Fiscales Proactivas y Hardening de Contenedores (COMPLETADA)
- [x] **Evolución del Modelo Outbox:** Añadir `next_retry_at` e índice compuesto `ix_outbox_events_dispatch` sobre `(status, next_retry_at, id)` en `models.py` y `schemas.py`.
- [x] **Módulo de Alertas Fiscales:** Implementar `fiscal_alerts.py` con esquema canónico ERP v1 y detección de anomalías (`fiscal.alert.cdr_rejected` y `fiscal.alert.spot_discrepancy`).
- [x] **Outbox Dispatcher Worker:** Desarrollar `src/caja_clara/dispatcher.py` con sondeo asíncrono no bloqueante, semáforo de concurrencia (`max_concurrent=5`), `httpx.AsyncClient`, backoff exponencial con jitter y clasificación de errores HTTP (2xx, 4xx, 5xx, DLQ).
- [x] **Observabilidad del Despacho:** Instrumentar métricas Prometheus (`OUTBOX_DELIVERY_DURATION_SECONDS`, `OUTBOX_DELIVERY_RETRIES_TOTAL`, `OUTBOX_EVENTS_TOTAL`, `FISCAL_ALERTS_TOTAL`).
- [x] **Hardening de Contenedores:** Configurar `Dockerfile` con usuario no privilegiado `appuser:10001`, orquestar servicio `dispatcher` en `docker-compose.yml` (`read_only: true`, `security_opt: [no-new-privileges:true]`, `cap_drop: [ALL]`, Cgroups 45MB) y crear `deploy/cajaclara-dispatcher.service`.
- [x] **Suite de Pruebas y Quality Gates:** 71 pruebas aprobadas (100% verde), 85.49% de cobertura real en `sqlite:///:memory:`.
