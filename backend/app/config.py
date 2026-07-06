import sys
from pydantic_settings import BaseSettings, SettingsConfigDict


def _is_packaged() -> bool:
    return getattr(sys, 'frozen', False)


class Settings(BaseSettings):
    # Packaged builds never load a bundled .env — no credentials belong in one;
    # every user's AlsoEnergy login lives only in their own browser session (see app/session.py).
    model_config = SettingsConfigDict(
        env_file=".env" if not _is_packaged() else None,
        env_file_encoding="utf-8",
    )

    alsoenergy_base_url: str = "https://api.alsoenergy.com"
    database_url: str = "sqlite:///./alsoenergy.db"

    # Session cookie is HttpOnly always; Secure requires HTTPS to actually reach the
    # browser — flip this on once the deployment sits behind TLS.
    session_cookie_secure: bool = False


settings = Settings()
