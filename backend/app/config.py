import sys
from pydantic_settings import BaseSettings, SettingsConfigDict


def _is_packaged() -> bool:
    return getattr(sys, 'frozen', False)


class Settings(BaseSettings):
    # .env is used in dev only; the packaged app loads credentials from keyring
    model_config = SettingsConfigDict(
        env_file=".env" if not _is_packaged() else None,
        env_file_encoding="utf-8",
    )

    alsoenergy_base_url: str = "https://api.alsoenergy.com"
    # Empty defaults — populated from keyring at runtime in packaged mode
    alsoenergy_username: str = ""
    alsoenergy_password: str = ""
    database_url: str = "sqlite:///./alsoenergy.db"


settings = Settings()
