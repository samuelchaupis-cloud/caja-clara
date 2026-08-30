"""
CLI Dashboard para monitorear el estado de CajaClara.
"""
import json
import os
import time

from rich import box
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from typing import Dict, Any, Optional

STATUS_FILE = "/var/lib/cajaclarad/status.json"
FALLBACK_STATUS_FILE = "status.json"

def get_status_data() -> Optional[Dict[str, Any]]:
    """Lee el archivo status.json de forma segura."""
    path = STATUS_FILE if os.path.exists(STATUS_FILE) else FALLBACK_STATUS_FILE
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None

def format_bytes(size: float) -> str:
    """Formatea bytes a KB/MB."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:3.1f} {unit}"
        size /= 1024.0
    return f"{size:3.1f} TB"

def generate_dashboard() -> Layout:
    """Genera el layout visual con los datos actuales."""
    data = get_status_data()
    
    if not data:
        return Panel(Text("Esperando datos del demonio...", style="bold red"), title="CajaClara Monitor")

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main")
    )
    layout["main"].split_row(
        Layout(name="metrics", ratio=2),
        Layout(name="status", ratio=1)
    )

    # Cabecera
    layout["header"].update(Panel(Text("CajaClara Daemon Monitor", justify="center", style="bold cyan")))

    # Tabla de métricas
    metrics_table = Table(box=box.SIMPLE, show_header=False)
    metrics_table.add_column("Métrica", style="bold")
    metrics_table.add_column("Valor")
    
    metrics_table.add_row("Correos Procesados", Text(str(data.get("emails_processed_total", 0)), style="green"))
    metrics_table.add_row("Errores de Extracción", Text(str(data.get("emails_errored_total", 0)), style="red" if data.get("emails_errored_total", 0) > 0 else "dim"))
    metrics_table.add_row("Último Ciclo Exitoso", str(data.get("last_successful_cycle", "N/A")))
    metrics_table.add_row("Tamaño de Base de Datos", format_bytes(data.get("db_size_bytes", 0)))
    
    layout["metrics"].update(Panel(metrics_table, title="Rendimiento"))

    # Tabla de estado
    status_table = Table(box=box.SIMPLE, show_header=False)
    status_table.add_column("Componente", style="bold")
    status_table.add_column("Estado")

    imap_status = data.get("imap_connection_status", "unknown")
    imap_style = "green" if imap_status == "connected" else "red"
    
    status_table.add_row("PID", str(data.get("pid", "N/A")))
    status_table.add_row("Uptime (s)", str(data.get("uptime_seconds", 0)))
    status_table.add_row("Conexión IMAP", Text(imap_status.upper(), style=imap_style))

    layout["status"].update(Panel(status_table, title="Estado del Sistema"))

    return layout

def main() -> None:
    """Bucle principal de la interfaz CLI."""
    with Live(generate_dashboard(), refresh_per_second=1) as live:
        try:
            while True:
                time.sleep(1)
                live.update(generate_dashboard())
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    main()
