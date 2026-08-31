# Findings: Fase 7 — Motor Fiscal UBL 2.1, Descompresión ZIP y Exportador Contable

## 1. Brecha de Dominio Resuelta
- **Problema de Costos y Latencia:** La extracción previa dependía exclusivamente de Gemini LLM para PDFs, lo que generaba un coste recurrente de tokens y latencia de ~3-5s por correo.
- **Estándar Fiscal en Latinoamérica:** En Perú (SUNAT), Colombia (DIAN) y México (SAT), los comprobantes válidos son archivos **XML UBL 2.1 / CFDI**, comúnmente comprimidos en archivos `.zip` junto a la Constancia de Recepción (CDR `R-*.xml`).
- **Invariante Financiero:** Se migran los montos de `float` (propenso a imprecisiones de coma flotante IEEE 754) a `Decimal` escalado para garantizar exactitud en conciliaciones contables.

## 2. Componentes de la Solución
1. **Parser UBL 2.1 Deterministico (`xml_parser.py`):**
   - Soporte para Facturas (01), Boletas (03), Notas de Crédito (07) y Notas de Débito (08).
   - Extracción de RUC, Razón Social, Serie-Correlativo, Fecha, Moneda, Base Gravada, IGV, Total y Detracciones (SPOT).
   - Validación de CDR (`ResponseCode == 0` de SUNAT).
   - Inmunidad a ataques XXE (`resolve_entities=False`).

2. **Módulo de Descompresión Segura en Memoria (`extractor.py`):**
   - Lectura de archivos `.zip` en memoria (`zipfile.ZipFile`).
   - Protección contra Zip Bombs (máx. 10MB descomprimidos, máx. 20 archivos).
   - Prioridad determinista: Si hay XML UBL -> procesamiento a coste $0; fallback a Gemini solo si es PDF escaneado sin XML.

3. **Exportador Contable Multiformato (`reports.py`):**
   - Generación de estructura oficial SIRE / RCE (Registro de Compras Electrónico - SUNAT).
   - Generación de CSV estructurado para importación en ERPs (Concar, Siigo, Excel).

4. **Saneamiento de Tests (Iron Law of Verification):**
   - Eliminación de `MagicMock` para la base de datos en `test_main.py`, reemplazado por SQLite `:memory:` real.
   - Tests de mutación y pruebas unitarias exhaustivas para UBL, ZIP, CDR y reportes.
