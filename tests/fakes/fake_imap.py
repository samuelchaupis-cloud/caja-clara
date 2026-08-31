from collections.abc import Generator


class FakeIMAPClient:
    def noop(self):
        return ("OK", [b""])


class FakeIDLE:
    def __init__(self):
        self.responses_to_emit = []
        self.should_raise = None

    def wait(self, timeout: int):
        if self.should_raise:
            raise self.should_raise
        if self.responses_to_emit:
            # Pop the first response
            return self.responses_to_emit.pop(0)
        return []


class FakeMailBox:
    def __init__(self, host, port=None, timeout=None, ssl_context=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.ssl_context = ssl_context

        self.is_logged_in = False
        self.logged_user = None
        self.client = FakeIMAPClient()
        self.idle = FakeIDLE()

        self.messages_store = []
        self.flagged_uids = []

        # Flags for testing failure scenarios
        self.fail_login = False
        self.fail_connect_count = 0
        self.current_connect_attempts = 0

    def login(self, user, password):
        if self.fail_login:
            raise RuntimeError("Invalid credentials (Fake)")
        self.is_logged_in = True
        self.logged_user = user

    def xoauth2(self, user, token):
        if self.fail_login:
            raise RuntimeError("Invalid XOAUTH2 token (Fake)")
        self.is_logged_in = True
        self.logged_user = user

    def fetch(self, criteria, mark_seen=False) -> Generator:
        if not self.is_logged_in:
            raise RuntimeError("FakeMailBox not logged in")
        # For our fake, we simply yield all messages currently in the store
        yield from self.messages_store

    def flag(self, uid, flag_set, value):
        if not self.is_logged_in:
            raise RuntimeError("FakeMailBox not logged in")
        self.flagged_uids.append((uid, flag_set, value))

    def logout(self):
        self.is_logged_in = False
