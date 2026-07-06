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
    "ALTER TABLE migration_jobs ADD COLUMN session_id TEXT NOT NULL DEFAULT ''",
]

# migration_jobs table is created by SQLModel.metadata.create_all; no ALTER needed

# Tables whose primary key gained a leading session_id column (multi-tenant isolation).
# SQLite can't ALTER a primary key in place, so if the old single-column-PK schema is
# still there we drop and let create_all() rebuild it fresh — these only ever hold a
# re-fetchable cache of AlsoEnergy data, never source-of-truth records.
_SESSION_SCOPED_TABLES = ["discovery_results", "hardware", "gateways", "sites"]


def _needs_session_id_rebuild(conn) -> bool:
    rows = conn.execute(text("PRAGMA table_info(sites)")).fetchall()
    if not rows:
        return False  # table doesn't exist yet — create_all() will make it correctly
    cols = {r[1] for r in rows}
    return "session_id" not in cols


def init_db() -> None:
    with engine.connect() as conn:
        if _needs_session_id_rebuild(conn):
            for tbl in _SESSION_SCOPED_TABLES:
                conn.execute(text(f"DROP TABLE IF EXISTS {tbl}"))
            conn.commit()

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
