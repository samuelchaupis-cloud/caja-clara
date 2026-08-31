import json
from unittest.mock import patch

from caja_clara.cli_monitor import export_to_csv, format_bytes, generate_dashboard, get_status_data


def test_format_bytes():
    """Valida el formateo de tamaños a unidades legibles."""
    assert format_bytes(500) == "500.0 B"
    assert format_bytes(2048) == "2.0 KB"
    assert format_bytes(1048576 * 5) == "5.0 MB"


def test_get_status_data_fallback(tmp_path):
    """Valida la lectura segura del archivo de estado."""
    status_file = tmp_path / "status.json"
    status_file.write_text(json.dumps({"emails_processed_total": 42}))

    with patch("caja_clara.cli_monitor.STATUS_FILE", str(status_file)):
        data = get_status_data()
        assert data is not None
        assert data["emails_processed_total"] == 42


def test_generate_dashboard_layout(tmp_path):
    """Valida la construcción de los widgets del dashboard terminal."""
    # 1. Caso sin datos
    with patch("caja_clara.cli_monitor.get_status_data", return_value=None):
        panel = generate_dashboard()
        assert panel is not None

    # 2. Caso con datos activos
    sample_data = {
        "emails_processed_total": 10,
        "emails_errored_total": 1,
        "last_successful_cycle": "2026-08-31T12:00:00",
        "db_size_bytes": 10240,
        "imap_connection_status": "connected",
        "pid": 1234,
        "uptime_seconds": 3600,
    }
    with patch("caja_clara.cli_monitor.get_status_data", return_value=sample_data):
        layout = generate_dashboard()
        assert layout is not None


def test_export_to_csv(tmp_path):
    """Valida la exportación por CLI a un archivo CSV."""
    out_file = str(tmp_path / "output.csv")
    with patch("caja_clara.cli_monitor.SessionLocal") as mock_session_cls:
        mock_db = mock_session_cls.return_value
        mock_db.query.return_value.filter_by.return_value.all.return_value = []
        export_to_csv(out_file)
        mock_db.close.assert_called_once()
