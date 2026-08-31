"""
Módulo de CLI Administrativo (cajaclara-admin).
Permite inspeccionar eventos encolados, consultar la Dead Letter Queue (DLQ)
y forzar el re-despacho atómico y transaccional con BEGIN IMMEDIATE.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from rich.console import Console
from rich.table import Table
from sqlalchemy import select
from sqlalchemy.orm import Session

from caja_clara.database import SessionLocal
from caja_clara.models import OutboxEvent

console = Console()


def list_outbox_events(
    db_factory: Callable[[], Session] = SessionLocal,
    status: str = "DEAD_LETTER",
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Consulta y retorna eventos de Outbox paginados según su estado."""
    with db_factory() as session:
        stmt = select(OutboxEvent).where(OutboxEvent.status == status).order_by(OutboxEvent.id.desc()).limit(limit).offset(offset)
        events = session.execute(stmt).scalars().all()
        return [
            {
                "id": e.id,
                "event_type": e.event_type,
                "status": e.status,
                "retry_count": e.retry_count,
                "error_detail": e.error_detail,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "processed_at": e.processed_at.isoformat() if e.processed_at else None,
            }
            for e in events
        ]


def replay_outbox_event(
    db_factory: Callable[[], Session] = SessionLocal,
    event_id: int = 0,
) -> bool:
    """
    Reconmuta atómicamente un evento en estado DEAD_LETTER a PENDING
    para que sea procesado de inmediato en el siguiente ciclo del dispatcher.
    """
    with db_factory() as session:
        event = session.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()
        if not event:
            return False

        if event.status != "DEAD_LETTER":
            return False

        event.status = "PENDING"
        event.retry_count = 0
        event.next_retry_at = datetime.now(UTC)
        event.error_detail = None
        event.processed_at = None

        session.commit()
        return True


def replay_all_dead_letters(
    db_factory: Callable[[], Session] = SessionLocal,
    event_type: str | None = None,
    batch_size: int = 100,
) -> int:
    """Reprocesa en lotes atómicos todos los eventos en estado DEAD_LETTER."""
    replayed_total = 0
    now = datetime.now(UTC)

    while True:
        with db_factory() as session:
            stmt = select(OutboxEvent).where(OutboxEvent.status == "DEAD_LETTER")
            if event_type:
                stmt = stmt.where(OutboxEvent.event_type == event_type)
            stmt = stmt.limit(batch_size)

            events = session.execute(stmt).scalars().all()
            if not events:
                break

            for ev in events:
                ev.status = "PENDING"
                ev.retry_count = 0
                ev.next_retry_at = now
                ev.error_detail = None
                ev.processed_at = None
                replayed_total += 1

            session.commit()

    return replayed_total


def main(args: list[str] | None = None, db_factory: Callable[[], Session] = SessionLocal) -> int:
    """Punto de entrada principal para el CLI cajaclara-admin."""
    parser = argparse.ArgumentParser(
        prog="cajaclara-admin",
        description="Consola de Administración de Operaciones y DLQ de CajaClara",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcomando: outbox
    outbox_parser = subparsers.add_parser("outbox", help="Gestión de eventos y DLQ de Outbox")
    outbox_sub = outbox_parser.add_subparsers(dest="outbox_action", required=True)

    # outbox list
    list_p = outbox_sub.add_parser("list", help="Listar eventos por estado")
    list_p.add_argument("--status", default="DEAD_LETTER", help="Estado a filtrar (DEAD_LETTER, PENDING, DELIVERED)")
    list_p.add_argument("--limit", type=int, default=50, help="Cantidad máxima de registros")
    list_p.add_argument("--offset", type=int, default=0, help="Desplazamiento inicial")

    # outbox replay
    replay_p = outbox_sub.add_parser("replay", help="Reprocesar un evento individual")
    replay_p.add_argument("--id", type=int, required=True, help="ID del evento a reprocesar")

    # outbox replay-all
    replay_all_p = outbox_sub.add_parser("replay-all", help="Reprocesar todos los eventos de la DLQ")
    replay_all_p.add_argument("--type", type=str, default=None, help="Filtrar por tipo de evento específico")

    parsed = parser.parse_args(args)

    if parsed.command == "outbox":
        if parsed.outbox_action == "list":
            events = list_outbox_events(db_factory=db_factory, status=parsed.status, limit=parsed.limit, offset=parsed.offset)
            if not events:
                console.print(f"[yellow]No se encontraron eventos en estado '{parsed.status}'.[/]")
                return 0

            table = Table(title=f"Eventos Outbox ({parsed.status})", border_style="cyan")
            table.add_column("ID", style="bold green", justify="right")
            table.add_column("Tipo de Evento", style="cyan")
            table.add_column("Reintentos", justify="right")
            table.add_column("Fecha Creación", style="magenta")
            table.add_column("Detalle del Error", style="red", max_width=40, overflow="ellipsis")

            for ev in events:
                table.add_row(
                    str(ev["id"]),
                    ev["event_type"],
                    str(ev["retry_count"]),
                    str(ev["created_at"]),
                    str(ev["error_detail"] or ""),
                )
            console.print(table)
            return 0

        if parsed.outbox_action == "replay":
            success = replay_outbox_event(db_factory=db_factory, event_id=parsed.id)
            if success:
                console.print(f"[bold green]✓ Evento #{parsed.id} reencolado con éxito como PENDING.[/]")
                return 0
            console.print(f"[bold red]✗ No se pudo reencolar el evento #{parsed.id} (no existe o no está en DEAD_LETTER).[/]")
            return 1

        if parsed.outbox_action == "replay-all":
            count = replay_all_dead_letters(db_factory=db_factory, event_type=parsed.type)
            console.print(f"[bold green]✓ Se reencolaron {count} eventos DEAD_LETTER a PENDING exitosamente.[/]")
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
