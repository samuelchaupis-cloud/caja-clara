# 🚀 Guía de Despliegue en Cloud (Fase 5)

Este documento te guiará paso a paso para desplegar **CajaClara** en un servidor virtual privado (VPS) como AWS EC2, DigitalOcean Droplet, o Google Cloud Compute Engine, para que opere ininterrumpidamente 24/7.

## Arquitectura de Producción
En tu servidor correrán tres microservicios administrados por Docker Compose:
1. **Daemon:** El proceso silencioso conectado al correo (IMAP IDLE) extrayendo facturas en tiempo real con IA.
2. **API:** El servidor FastAPI protegido que expone los datos a tu ERP.
3. **Proxy Inverso (Caddy):** Capa de red expuesta a internet en los puertos 80 y 443 que genera automáticamente el certificado SSL (candado verde HTTPS) para tu dominio.

---

## Paso 1: Preparar el Servidor Virtual (VPS)

1. Alquila un VPS básico (por ejemplo, 1GB RAM, 1 vCPU en Ubuntu 24.04).
2. Abre los puertos **80 (HTTP)** y **443 (HTTPS)** en el firewall o grupos de seguridad del proveedor en la nube.
3. Conéctate a tu servidor por SSH.

## Paso 2: Instalar Dependencias del Servidor

Ejecuta estos comandos en tu servidor Ubuntu/Debian para instalar Docker y Git:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl

# Instalar Docker oficial
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Aplica los permisos (o cierra sesión y vuelve a entrar)
newgrp docker
```

## Paso 3: Clonar el Repositorio

```bash
git clone https://github.com/samuelchaupis-cloud/caja-clara.git
cd caja-clara
```

## Paso 4: Configurar Credenciales y Dominio

1. Copia el archivo de entorno o créalo:
   ```bash
   nano .env
   ```
2. Pega la siguiente estructura y llénala con tus datos reales:
   ```env
   CAJACLARAD_IMAP_HOST=imap.gmail.com
   CAJACLARAD_IMAP_USER=tucorreo@empresa.com
   CAJACLARAD_IMAP_PASSWORD=password_de_aplicacion
   CAJACLARAD_AI_API_KEY=tu_api_key_de_google_gemini
   CAJACLARAD_API_KEY=una_contraseña_muy_larga_y_segura_para_la_api
   
   # Configuración de Dominio para Caddy
   # Si ya compraste un dominio y lo apuntaste a la IP del VPS, ponlo aquí (ej. api.miempresa.com). 
   # Caddy emitirá el certificado SSL HTTPS automáticamente.
   # Si aún no tienes dominio, pon la IP pública del servidor (ej. 192.168.1.50)
   DOMAIN=api.miempresa.com 
   ```
3. Guarda el archivo (`Ctrl+O`, `Enter`, `Ctrl+X`).

## Paso 5: Despliegue con Un Solo Clic

Dale permisos de ejecución al script y lánzalo:

```bash
chmod +x deploy.sh
./deploy.sh
```

¡Eso es todo! Verás que Docker descarga las imágenes y levanta la plataforma. 

## Paso 6: Verificación y Consumo

Para verificar que los logs estén limpios:
```bash
docker compose logs -f
```

Para consumir tu API desde cualquier parte del mundo de forma segura:
```bash
curl -H "X-API-Key: tu_llave_maestra" https://api.miempresa.com/api/v1/invoices
```
*(Reemplaza `https://api.miempresa.com` por tu IP local si aún no has apuntado el dominio).*
