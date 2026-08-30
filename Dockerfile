# Imagen oficial y optimizada para proyectos en Python (Debian-based)
FROM python:3.12-slim-bookworm

# Variables de entorno para Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

# Instalar 'uv' utilizando su instalador oficial hiper-rápido
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Configurar directorio de trabajo
WORKDIR /app

# Copiar archivos de dependencias primero para cachear la capa
COPY pyproject.toml uv.lock ./

# Sincronizar e instalar dependencias (usando el resolver súper rápido de uv)
RUN uv sync --frozen --no-dev

# Copiar el código fuente completo
COPY . .

# Por defecto arrancaremos el demonio (docker-compose sobrescribirá esto para la API)
CMD ["uv", "run", "cajaclarad"]
