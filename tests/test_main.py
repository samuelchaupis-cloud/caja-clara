import os
import signal
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import IntegrityError

from caja_clara.main import _handle_signal, process_mailbox, shutdown_event, write_status_file


@patch("caja_clara.main.os.replace")
def test_write_status_file(mock_replace):
    """Test metrics are written atomically to status.json."""
    write_status_file()
    mock_replace.assert_called_once()
    # Check that a tmp file was created
    assert os.path.exists("status.json.tmp") or os.path.exists("/var/lib/cajaclarad/status.json.tmp")

def test_handle_signal():
    """Test that signals correctly set the shutdown event."""
    shutdown_event.clear()
    _handle_signal(signal.SIGINT, None)
    assert shutdown_event.is_set()

@patch("caja_clara.main.get_db")
@patch("caja_clara.main.extract_email_data")
def test_process_mailbox_deduplication(mock_extract, mock_get_db):
    """Test that IntegrityError rolls back the DB but still marks as seen in IMAP."""
    # Setup mocks
    mock_client = MagicMock()
    mock_msg = MagicMock()
    mock_msg.uid = "123"
    mock_client.fetch_unseen.return_value = [mock_msg]
    
    mock_extract.return_value = (MagicMock(model_dump=lambda: {"message_id": "<dup>"}), None)
    
    mock_db = MagicMock()
    mock_db.commit.side_effect = [IntegrityError("Dup", params=[], orig=Exception()), None]
    mock_get_db.return_value = iter([mock_db])
    
    # Run
    shutdown_event.clear()
    process_mailbox(mock_client)
    
    # Assert rollback was called for the row, but mark_seen was still executed to skip it next time
    mock_db.rollback.assert_called_once()
    mock_client.mark_seen.assert_called_once_with("123")
