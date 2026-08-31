# Imagen oficial y optimizada para proyectos en Python (Debian-based)
FROM python:3.12-slim-bookworm

# Variables de entorno para Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

# Crear usuario y grupo de sistema sin privilegios (Hardening OWASP)
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /sbin/nologin -M -d /app appuser

# Instalar 'uv' utilizando su instalador oficial hiper-rápido
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Configurar directorio de trabajo
WORKDIR /app

# Crear directorio de datos con permisos estrictos
RUN mkdir -p /app/data && chown -R appuser:appgroup /app

# Copiar archivos de dependencias primero para cachear la capa
COPY pyproject.toml uv.lock ./

# Sincronizar e instalar dependencias
RUN uv sync --frozen --no-dev

# Copiar el código fuente completo
COPY . .
RUN chown -R appuser:appgroup /app

USER 10001:10001

# Por defecto arrancaremos el demonio (docker-compose sobrescribirá esto para la API o Dispatcher)
CMD ["uv", "run", "cajaclarad"]
