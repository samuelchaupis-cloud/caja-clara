# Task Plan: CajaClara — Plataforma Fiscal y Concurrencia Enterprise

**Estado General:** Fases 7, 8, 9, 10 y 11 completadas al 100% (91 tests en verde, 85.14% de cobertura real sin mocks).

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

---

### ✅ Fase 10: Multi-Buzón Concurrente, Ledger Inmutable y Blindaje de Memoria (COMPLETADA)
- [x] **Inmutabilidad y Triggers SQL:** Implementar `setup_sqlite_immutability_triggers` con triggers `BEFORE UPDATE` y `BEFORE DELETE` en `database.py` que abortan con `IntegrityError` ante mutaciones en registros `PROCESSED`.
- [x] **Restricción CheckConstraint & Notas de Crédito:** Añadir `CheckConstraint` para `document_type` en `models.py` y campos de referencia contable (`reference_document_type`, `reference_invoice_number`, `discrepancy_code`, `discrepancy_reason`) en `models.py`, `schemas.py` y `xml_parser.py`.
- [x] **Dominio Decimal Estricto:** Erradicar todo uso de `float()` en `fiscal_alerts.py` y `schemas.py`, asegurando formateo exacto de strings decimales y validación de cuadratura contable.
- [x] **Hardening de Memoria y Streaming:** Reducir `MAX_ATTACHMENT_SIZE_BYTES` a 8MB en `constants.py` y descompresión ZIP por bloques de 64KB con cuota en tiempo real en `extractor.py`.
- [x] **Orquestador Multi-Buzón:** Desarrollar `MailboxPoolOrchestrator` y `MailboxWorker` en `src/caja_clara/mailbox_pool.py` con supervisión concurrente y aislamiento de fallos $N-1$ inmunes.
- [x] **Observabilidad Multi-Buzón:** Instrumentar `MAILBOX_STATUS`, `MAILBOX_INVOICES_TOTAL` y `RESIDENT_MEMORY_BYTES` en `metrics.py`.
- [x] **Suite de Pruebas CoVe & Caos:** 82 pruebas aprobadas (100% verde), 85.06% de cobertura real en `sqlite:///:memory:` y auditoría Code Breaker superada con 0 defectos.

---

### ✅ Fase 11: Replicación Litestream a Cloudflare R2/S3, Health Probes Seguras y Resiliencia Distribuida (COMPLETADA)
- [x] **Variables de Entorno Litestream:** Configuración de `Settings` en `src/caja_clara/config.py` con soporte para endpoints, buckets y llaves S3/R2.
- [x] **Métricas de Replicación Prometheus:** Implementar en `src/caja_clara/metrics.py`: `LITESTREAM_LAG_SECONDS`, `REPLICATION_STATUS`, `LAST_SNAPSHOT_TIMESTAMP` y `REPLICATION_SYNC_ERRORS_TOTAL`.
- [x] **Sanitización de Health Probes (CWE-209):** Refactorizar `/health/ready` en `src/caja_clara/api.py` para devolver `HTTP 503` sanitizado sin volcado de rutas ni excepciones SQLite.
- [x] **Endpoint de Telemetría de Réplica:** Implementar `/health/replication` público con lag en segundos y `/api/v1/health/replica` administrativo protegido por `X-API-Key`.
- [x] **Endurecimiento de Logs contra Fugas de Secretos:** Implementar en `redact_pii` filtrado recursivo de estructuras anidadas y matching de claves S3/R2 (`litestream_secret_key`, `access_key_id`, etc.).
- [x] **Hardening de Servicios en Docker Compose:** Configurar `read_only: true`, `cap_drop: [ALL]` y `tmpfs` en `cajaclarad` y `api`.
- [x] **Inversión Red-Green y Suite de Pruebas:** 91 pruebas aprobadas (100% verde), 85.14% de cobertura real y auditoría Code Breaker certificada sin fallos.

---

### ✅ Fase 12: Hub de Integraciones ERP, Webhooks Certificados & Administración DLQ (COMPLETADA)
- [x] **Adaptadores y Contratos ERP:** Desarrollar `src/caja_clara/erp_adapters.py` con transformaciones canónicas hacia Odoo (`account.move`), SAP Business One (`PurchaseInvoices` con UDFs SPOT) y Siigo Cloud.
- [x] **Notificaciones Multi-Canal Desacopladas:** Implementar `src/caja_clara/notifications.py` con formateo y despacho resiliente para Telegram y WhatsApp con aislamiento total de fallos.
- [x] **CLI de Gestión de DLQ:** Desarrollar `src/caja_clara/cli_admin.py` (`cajaclara-admin outbox list`, `replay`, `replay-all`) con `BEGIN IMMEDIATE` y registrar en `pyproject.toml`.
- [x] **Manejo de Throttling y Resiliencia en Dispatcher:** Soporte para cabecera `Retry-After` en `HTTP 429`, sweeper de eventos huérfanos en `PROCESSING` y despacho opcional de alertas fiscales.
- [x] **Inversión Red-Green y 4 Quality Gates:** Mutación determinista demostrada, 104 pruebas aprobadas (100% verde), 85.61% de cobertura real en SQLite `:memory:`, 0 errores Ruff, 0 errores Mypy y 0 vulnerabilidades Bandit.
