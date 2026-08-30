# CajaClara

> **Del correo a la contabilidad. Sin humanos. Sin errores. Sin facturas perdidas.**

---

## El Problema

Cada semana, los contadores y gerentes de Pymes dedican entre **5 y 10 horas** a una tarea que no debería existir: abrir su bandeja de entrada, buscar correos de proveedores, descargar facturas adjuntas, copiar datos a una hoja de cálculo y rezar para no olvidar ninguna.

El costo real no son las horas. Es la **factura que se pierde**, la que no se declara, la que genera una multa fiscal o un descuadre contable que nadie detecta hasta que es demasiado tarde.

## La Solución

**CajaClara** es un demonio Linux que elimina este problema de raíz.

Se conecta de forma segura al correo de la empresa vía IMAP, monitorea la bandeja 24/7, identifica automáticamente los correos con facturas y extrae toda la metadata relevante a una base de datos local estructurada — lista para consultar, exportar o integrar con cualquier sistema contable.

**Cero intervención humana. Cero facturas perdidas. Cero fricción de despliegue.**

### Capacidades Clave

| Capacidad | Detalle |
|---|---|
| **Extracción automática** | Sender, fecha, asunto, adjuntos, hash de contenido |
| **Idempotencia** | Deduplicación por `Message-ID` RFC 2822 — nunca duplica, nunca pierde |
| **Tolerancia a fallos** | Reconexión IMAP con backoff exponencial, transacciones atómicas SQLite WAL |
| **Apagado elegante** | Manejo de `SIGTERM`/`SIGINT` con cierre ordenado de conexiones |
| **Seguridad** | TLS verificado, credenciales vía env vars, redacción de PII en logs |
| **Operabilidad** | Unit systemd con hardening, logging estructurado JSON, archivo de health check |

---

## Stack Tecnológico

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.12+ |
| Gestión de paquetes | [`uv`](https://docs.astral.sh/uv/) (Astral) |
| Conexión IMAP | `imap-tools` |
| Base de datos | SQLite (WAL mode) + SQLAlchemy 2.0 |
| Migraciones | Alembic |
| Validación | Pydantic v2 |
| Logging | `structlog` (JSON) |
| Resiliencia | `tenacity` (exponential backoff) |
| Orquestación | systemd |

---

## Inicio Rápido (Desarrolladores)

### Prerrequisitos

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) instalado

### Setup en 3 comandos

```bash
# 1. Clonar e instalar dependencias (incluye dev)
git clone https://github.com/tu-org/caja-clara.git
cd caja-clara
uv sync

# 2. Ejecutar tests para verificar que todo funciona
uv run pytest tests/ -v

# 3. Ejecutar el demonio localmente (requiere variables de entorno)
cp .env.example .env   # Editar con credenciales de prueba
uv run cajaclarad
```

### Variables de Entorno

```bash
CAJACLARAD_IMAP_HOST=imap.example.com
CAJACLARAD_IMAP_PORT=993
CAJACLARAD_IMAP_USER=facturas@example.com
CAJACLARAD_IMAP_PASSWORD=tu-app-password
CAJACLARAD_DB_PATH=./dev.db
CAJACLARAD_POLL_INTERVAL=120
CAJACLARAD_LOG_LEVEL=DEBUG
```

### Comandos Frecuentes

```bash
# Linting y formateo
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/

# Tests con cobertura
uv run pytest tests/ -v --cov=src/caja_clara --cov-report=term-missing

# Auditoría de seguridad
uv run bandit -r src/ -ll -ii

# Migraciones de base de datos
uv run alembic revision --autogenerate -m "descripción del cambio"
uv run alembic upgrade head

# QA completa (pre-commit)
bash .agents/scripts/pre_commit_gate.sh
```

---

## Despliegue en Producción

```bash
# En el servidor Linux
cd /opt/cajaclarad
git pull origin main
uv sync --frozen
uv run alembic upgrade head
sudo systemctl restart cajaclarad
sudo journalctl -u cajaclarad -f
```

Consultar [`docs/OPERATIONS.md`](docs/OPERATIONS.md) para la guía operativa completa, incluyendo creación del usuario de sistema, permisos de archivos y hardening de systemd.

---

## Arquitectura

```
┌─────────────┐    TLS/993     ┌──────────────┐    SQLAlchemy    ┌────────────┐
│  Servidor   │◄──────────────►│  cajaclarad   │◄───────────────►│  SQLite    │
│  IMAP       │   imap-tools   │  (Python)     │   WAL mode      │  (local)   │
└─────────────┘                └──────┬───────┘                 └────────────┘
                                      │
                               ┌──────┴───────┐
                               │   systemd     │
                               │  (supervisor) │
                               └──────────────┘
```

Detalles técnicos completos en [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md).

---

## Licencia

MIT
