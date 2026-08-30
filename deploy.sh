#!/bin/bash
# Script de despliegue automático para servidores Cloud (VPS)

set -e

echo "=========================================="
echo "🚀 Iniciando despliegue de CajaClara SaaS"
echo "=========================================="

# 1. Asegurar que estamos en el directorio correcto
cd "$(dirname "$0")"

# 2. Descargar los últimos cambios de GitHub
echo "[1/4] Descargando últimas actualizaciones..."
git pull origin main

# 3. Validar existencia del archivo .env
if [ ! -f ".env" ]; then
    echo "⚠️ ADVERTENCIA: No se encontró el archivo .env."
    echo "Creando uno a partir de un template..."
    cat <<EOF > .env
CAJACLARAD_IMAP_HOST=imap.tuservidor.com
CAJACLARAD_IMAP_USER=facturas@tudominio.com
CAJACLARAD_IMAP_PASSWORD=tu_password_seguro
CAJACLARAD_AI_API_KEY=tu_api_key_de_google_gemini
CAJACLARAD_API_KEY=llave_maestra_segura_para_fastapi
DOMAIN=localhost
EOF
    echo "Por favor, detén este script (Ctrl+C), edita el archivo .env con tus credenciales reales y vuelve a ejecutar ./deploy.sh"
    exit 1
fi

# 4. Reconstruir imágenes limpias
echo "[2/4] Construyendo imágenes de Docker optimizadas..."
docker compose build --pull

# 5. Desplegar
echo "[3/4] Levantando servicios (Demonio + API + Proxy)..."
docker compose up -d

# 6. Limpieza
echo "[4/4] Limpiando imágenes huérfanas..."
docker image prune -f

echo "=========================================="
echo "✅ Despliegue completado con éxito."
echo "Puedes ver los logs en vivo ejecutando: docker compose logs -f"
echo "=========================================="
