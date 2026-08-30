# Guía Operativa: CajaClara

## 1. Creación del entorno

CajaClara se ejecuta bajo un usuario sin privilegios.

```bash
sudo useradd -r -s /usr/sbin/nologin cajaclarad
sudo mkdir -p /var/lib/cajaclarad /var/log/cajaclarad /etc/cajaclarad
sudo chown cajaclarad:cajaclarad /var/lib/cajaclarad /var/log/cajaclarad
sudo chmod 700 /var/lib/cajaclarad
sudo chmod 750 /var/log/cajaclarad
```

## 2. Inyección de Credenciales

Crea el archivo `/etc/cajaclarad/env` y configura sus permisos estrictamente:

```bash
sudo nano /etc/cajaclarad/env
# Agrega las variables (ver .env.example)

sudo chown cajaclarad:cajaclarad /etc/cajaclarad/env
sudo chmod 600 /etc/cajaclarad/env
```

## 3. Instalación de la Aplicación

```bash
cd /opt
sudo git clone https://github.com/tu-org/caja-clara.git cajaclarad
sudo chown -R cajaclarad:cajaclarad cajaclarad
cd cajaclarad
sudo -u cajaclarad uv sync --frozen
sudo -u cajaclarad uv run alembic upgrade head
```

## 4. Orquestación con systemd

Instalar el servicio:

```bash
sudo cp /opt/cajaclarad/deploy/cajaclarad.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable cajaclarad
sudo systemctl start cajaclarad
```

## 5. Monitoreo y Logs

Ver los logs en tiempo real:

```bash
sudo journalctl -u cajaclarad -f
```

Verificar el estado interno (Health Check):

```bash
sudo cat /var/lib/cajaclarad/status.json | jq
```

## 6. Backup de la Base de Datos

SQLite en modo WAL requiere un backup atómico para no corromper datos. No uses `cp`. Usa:

```bash
sqlite3 /var/lib/cajaclarad/cajaclarad.db ".backup '/path/to/backup/cajaclarad_$(date +%Y%m%d).db'"
```
