"""
Per-browser-session state: AlsoEnergy credentials + OAuth token.

Every visitor gets a random session id (delivered via an HttpOnly cookie) that maps
to one UserSession, held only in process memory. Nothing here is ever written to
disk, and no two sessions ever share a UserSession instance — that's what keeps one
tenant's credentials and API calls from leaking into another's. Restarting the
backend or losing the cookie discards the session; the user just re-enters
credentials, same as reopening the desktop app today.
"""
import secrets
import time
from dataclasses import dataclass, field

SESSION_COOKIE = "ae_session"
_IDLE_TIMEOUT_SECONDS = 24 * 60 * 60


@dataclass
class UserSession:
    session_id: str
    username: str = ""
    password: str = ""
    access_token: str | None = None
    token_expires_at: float = 0.0  # monotonic clock
    last_seen: float = field(default_factory=time.time)

    def has_credentials(self) -> bool:
        return bool(self.username and self.password)

    def set_credentials(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        # A new credential set invalidates any token issued for the old one.
        self.access_token = None
        self.token_expires_at = 0.0

    def clear_credentials(self) -> None:
        self.username = ""
        self.password = ""
        self.access_token = None
        self.token_expires_at = 0.0

    def token_status(self) -> dict:
        if self.access_token is None:
            return {"status": "not_authenticated"}
        if time.monotonic() >= self.token_expires_at - 60:
            return {"status": "expired"}
        remaining = int(self.token_expires_at - time.monotonic())
        return {"status": "valid", "expires_in_seconds": remaining}


_sessions: dict[str, UserSession] = {}


def _sweep_idle() -> None:
    cutoff = time.time() - _IDLE_TIMEOUT_SECONDS
    stale = [sid for sid, s in _sessions.items() if s.last_seen < cutoff]
    for sid in stale:
        _sessions.pop(sid, None)


def get_or_create(session_id: str | None) -> tuple[UserSession, bool]:
    """Return (session, is_new_session)."""
    if session_id:
        existing = _sessions.get(session_id)
        if existing:
            existing.last_seen = time.time()
            return existing, False

    _sweep_idle()
    new_id = secrets.token_urlsafe(32)
    sess = UserSession(session_id=new_id)
    _sessions[new_id] = sess
    return sess, True
