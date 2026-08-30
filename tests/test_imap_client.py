from unittest.mock import MagicMock, patch

from caja_clara.imap_client import IMAPClient


@patch("caja_clara.imap_client.MailBox")
@patch("caja_clara.imap_client.ssl.create_default_context")
def test_imap_connect_tls_verified(mock_ssl_context, mock_mailbox):
    """Test that IMAPClient connects with a verified TLS context."""
    client = IMAPClient()
    
    mock_ctx_instance = MagicMock()
    mock_ssl_context.return_value = mock_ctx_instance
    mock_mailbox_instance = MagicMock()
    mock_mailbox.return_value = mock_mailbox_instance
    
    client.connect()
    
    # Assert TLS context was created and passed
    mock_ssl_context.assert_called_once()
    mock_mailbox.assert_called_once_with(
        client._host, port=client._port, timeout=30, ssl_context=mock_ctx_instance
    )
    mock_mailbox_instance.login.assert_called_once_with(client._user, client._password)

@patch("caja_clara.imap_client.MailBox")
def test_imap_reconnect_retry(mock_mailbox):
    """Test that IMAPClient retries on failure."""
    # Force the mock to fail twice, then succeed
    mock_mailbox_instance = MagicMock()
    mock_mailbox.side_effect = [Exception("Net Error"), Exception("Net Error"), mock_mailbox_instance]
    
    client = IMAPClient()
    client.connect()
    
    assert mock_mailbox.call_count == 3
    mock_mailbox_instance.login.assert_called_once()
