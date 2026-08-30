"""
IMAP Client for connecting and interacting with mail servers securely.
"""
import logging
import ssl
from collections.abc import Generator

from imap_tools import A, MailBox, MailMessage
from tenacity import retry, stop_after_attempt, wait_exponential, wait_random

from caja_clara.config import config

logger = logging.getLogger(__name__)


class IMAPClient:
    def __init__(self):
        self._host = config.imap_host
        self._port = config.imap_port
        self._user = config.imap_user
        self._password = config.imap_password
        self._mailbox = None

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=120) + wait_random(0, 5),
        reraise=True,
    )
    def connect(self) -> None:
        """Establish an IMAP connection with verified TLS."""
        logger.info("Conectando a IMAP...", host=self._host, port=self._port)
        
        # TLS Certificate Verification is MANDATORY.
        # NEVER use ssl.CERT_NONE or check_hostname=False in production.
        ctx = ssl.create_default_context()
        
        # connect args
        # 30s timeout on connect/read operations
        self._mailbox = MailBox(
            self._host, port=self._port, timeout=30, ssl_context=ctx
        )
        self._mailbox.login(self._user, self._password)
        logger.info("Autenticación IMAP exitosa.")

    def fetch_unseen(self) -> Generator[MailMessage, None, None]:
        """Fetch unread emails without marking them as read initially."""
        if not self._mailbox:
            raise RuntimeError("Not connected to IMAP.")
        
        logger.debug("Buscando correos no leídos (UNSEEN)...")
        # Ensure connection is alive before fetching
        self._mailbox.client.noop()
        
        # mark_seen=False is critical to guarantee idempotency in case of crashes
        for msg in self._mailbox.fetch(A(seen=False), mark_seen=False):
            yield msg

    def mark_seen(self, uid: str) -> None:
        """Mark a specific message as read."""
        if not self._mailbox:
            raise RuntimeError("Not connected to IMAP.")
        self._mailbox.flag(uid, ["\\Seen"], True)
        logger.debug(f"Mensaje {uid} marcado como leído.")

    def logout(self) -> None:
        """Cleanly close the IMAP connection."""
        if self._mailbox:
            try:
                self._mailbox.logout()
            except Exception as e:
                logger.warning(f"Error durante IMAP logout: {e}")
            finally:
                self._mailbox = None
                logger.info("Conexión IMAP cerrada.")
