"""
Cliente IMAP con resiliencia, verificación TLS estricta y soporte IDLE para conectar e interactuar con servidores de correo de forma segura.
"""
import ssl
from collections.abc import Generator

import structlog
from imap_tools import A, MailBox, MailMessage
from tenacity import retry, stop_after_attempt, wait_exponential, wait_random

from caja_clara.config import config

logger = structlog.get_logger()


class IMAPClient:
    def __init__(self) -> None:
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
        """Establece una conexión IMAP segura con verificación TLS obligatoria."""
        logger.info("intentando_conexion_imap", host=self._host, port=self._port)

        # La verificación de certificado TLS es OBLIGATORIA.
        # NUNCA deshabilitar check_hostname ni usar CERT_NONE en producción.
        ctx = ssl.create_default_context()
        
        # connect args
        # 30s timeout on connect/read operations
        self._mailbox = MailBox(
            self._host, port=self._port, timeout=30, ssl_context=ctx
        )
        if config.imap_oauth2_token:
            # Autenticación moderna XOAUTH2 para proveedores cloud
            logger.info("autenticando_via_xoauth2")
            self._mailbox.xoauth2(self._user, config.imap_oauth2_token)
        elif self._password:
            self._mailbox.login(self._user, self._password)
        else:
            raise ValueError("No se proveyó password ni token oauth2")
            
        logger.info("autenticacion_imap_exitosa")

    def fetch_unseen(self) -> Generator[MailMessage, None, None]:
        """Generador que produce mensajes de correo no leídos."""
        if not self._mailbox:
            raise RuntimeError("No hay conexión IMAP establecida.")
        
        # Ensure connection is alive before fetching
        self._mailbox.client.noop()
        
        # mark_seen=False es crítico para garantizar idempotencia en caso de crashes
        for msg in self._mailbox.fetch(A(seen=False), mark_seen=False):
            yield msg

    def wait_for_new_messages(self, timeout: int = 60) -> bool:
        """
        Bloquea usando IMAP IDLE hasta recibir un nuevo evento.
        Retorna True si hay eventos, False si el timeout expiró.
        Hace fallback elegante si el servidor no soporta IDLE.
        """
        if not self._mailbox:
            raise RuntimeError("No hay conexión IMAP establecida.")
        
        try:
            logger.debug("entrando_estado_idle")
            responses = self._mailbox.idle.wait(timeout=timeout)
            return bool(responses)
        except Exception as e:
            logger.warning("error_imap_idle_fallback", error=str(e))
            import time
            time.sleep(timeout)
            return True

    def mark_seen(self, uid: str) -> None:
        """Marca un mensaje específico como leído."""
        if not self._mailbox:
            raise RuntimeError("No hay conexión IMAP establecida.")
        self._mailbox.flag(uid, ["\\Seen"], True)
        logger.debug("mensaje_marcado_leido", uid=uid)

    def logout(self) -> None:
        """Cierra la conexión al servidor IMAP de forma segura."""
        if self._mailbox:
            try:
                self._mailbox.logout()
            except Exception as e:
                logger.warning("error_durante_logout_imap", error=str(e))
            finally:
                self._mailbox = None
                logger.info("Conexión IMAP cerrada.")
