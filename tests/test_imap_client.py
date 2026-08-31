from unittest.mock import patch

import pytest

from caja_clara.config import config
from caja_clara.imap_client import IMAPClient
from tests.fakes.fake_imap import FakeMailBox


@pytest.fixture
def fake_mailbox():
    return FakeMailBox("imap.example.com")


def test_imap_connect_tls_verified(fake_mailbox):
    """Test that IMAPClient connects and authenticates correctly using FakeMailBox."""
    client = IMAPClient()

    # We patch the MailBox instantiation to return our FakeMailBox
    with (
        patch("caja_clara.imap_client.MailBox", return_value=fake_mailbox),
        patch("caja_clara.imap_client.ssl.create_default_context") as mock_ssl,
    ):
        client.connect()

        # State 1 -> State 2 (Authenticating) -> State 3 (Connected)
        assert mock_ssl.call_count == 1
        assert fake_mailbox.is_logged_in is True
        assert fake_mailbox.logged_user == config.imap_user
        assert client._mailbox is fake_mailbox


def test_imap_reconnect_retry():
    """Test that IMAPClient retries on failure (State 5 Error/Reconnect)."""
    # Create a FakeMailBox that raises Exception for the first 2 logins, then succeeds
    mailbox_fake = FakeMailBox("imap.example.com")

    # We will simulate the network failure by patching MailBox directly with a side effect for the constructor,
    # but since IMAPClient instantiates MailBox inside the retry loop, we can just intercept the MailBox class.

    call_counts = {"attempts": 0}

    def fake_mailbox_factory(*args, **kwargs):
        call_counts["attempts"] += 1
        if call_counts["attempts"] < 3:
            raise RuntimeError("Net Error")
        return mailbox_fake

    client = IMAPClient()
    with patch("caja_clara.imap_client.MailBox", side_effect=fake_mailbox_factory):
        client.connect()

        # Should have failed 2 times and succeeded on the 3rd
        assert call_counts["attempts"] == 3
        assert mailbox_fake.is_logged_in is True


def test_imap_fetch_unseen_and_mark(fake_mailbox):
    """Test State 4: Fetching and Processing."""
    client = IMAPClient()
    with patch("caja_clara.imap_client.MailBox", return_value=fake_mailbox):
        client.connect()

        # Inject some fake messages
        fake_mailbox.messages_store = ["msg1", "msg2"]

        fetched = list(client.fetch_unseen())
        assert len(fetched) == 2
        assert fetched == ["msg1", "msg2"]

        # Test marking as seen
        client.mark_seen("12345")
        assert len(fake_mailbox.flagged_uids) == 1
        assert fake_mailbox.flagged_uids[0][0] == "12345"


def test_imap_idle_wait(fake_mailbox):
    """Test State 3: IDLE waiting."""
    client = IMAPClient()
    with patch("caja_clara.imap_client.MailBox", return_value=fake_mailbox):
        client.connect()

        # Configure Fake IDLE to simulate incoming message
        fake_mailbox.idle.responses_to_emit.append([b"EXISTS"])

        result = client.wait_for_new_messages(timeout=1)
        assert result is True

        # Test timeout with no responses
        result_empty = client.wait_for_new_messages(timeout=1)
        assert result_empty is False


def test_imap_logout(fake_mailbox):
    """Test graceful disconnection."""
    client = IMAPClient()
    with patch("caja_clara.imap_client.MailBox", return_value=fake_mailbox):
        client.connect()
        assert fake_mailbox.is_logged_in is True

        client.logout()
        assert fake_mailbox.is_logged_in is False
        assert client._mailbox is None
