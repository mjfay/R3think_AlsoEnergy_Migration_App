from sqlalchemy import text
from sqlmodel import SQLModel, Session, create_engine

from app.config import settings

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False},
)

# New nullable columns added to existing tables. SQLite supports ADD COLUMN
# for nullable/defaulted columns without dropping the table.
_HARDWARE_MIGRATIONS = [
    "ALTER TABLE hardware ADD COLUMN ip_address TEXT",
    "ALTER TABLE hardware ADD COLUMN port INTEGER",
    "ALTER TABLE hardware ADD COLUMN port_mode TEXT",
    "ALTER TABLE hardware ADD COLUMN gateway_id TEXT",
    "ALTER TABLE hardware ADD COLUMN driver_name TEXT",
    "ALTER TABLE hardware ADD COLUMN driver_settings_json TEXT NOT NULL DEFAULT '{}'",
    "ALTER TABLE hardware ADD COLUMN register_groups_json TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE hardware ADD COLUMN is_virtual_device INTEGER NOT NULL DEFAULT 0",
    # Extracted from driver.settings for fast CSV access
    "ALTER TABLE hardware ADD COLUMN modbus_unit_id TEXT",
    "ALTER TABLE hardware ADD COLUMN tcp_port TEXT",
]

_JOB_MIGRATIONS = [
    "ALTER TABLE migration_jobs ADD COLUMN include_data_devices INTEGER NOT NULL DEFAULT 1",
]

# migration_jobs table is created by SQLModel.metadata.create_all; no ALTER needed


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    # Run additive migrations — ignore "duplicate column" errors silently
    with engine.connect() as conn:
        for stmt in _HARDWARE_MIGRATIONS + _JOB_MIGRATIONS:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass  # column already exists


def get_session():
    with Session(engine) as session:
        yield session
