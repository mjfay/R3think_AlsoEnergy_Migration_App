import json
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


# Job status values
JOB_STATUS_PENDING = "pending"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_DONE = "done"
JOB_STATUS_ERROR = "error"
JOB_STATUS_CANCELLED = "cancelled"
JOB_STATUS_EMAILED = "emailed"


class Site(SQLModel, table=True):
    __tablename__ = "sites"

    site_id: int = Field(primary_key=True)
    site_name: str = ""
    customer_id: Optional[int] = None
    timezone: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    install_date: Optional[str] = None
    turn_on_date: Optional[str] = None
    system_size_kw: Optional[float] = None
    raw_json: str = "{}"
    last_synced: Optional[datetime] = None


class Hardware(SQLModel, table=True):
    __tablename__ = "hardware"

    id: int = Field(primary_key=True)
    site_id: int = Field(foreign_key="sites.site_id", index=True)
    name: str = ""
    string_id: Optional[str] = None
    function_code: Optional[str] = None
    serial_number: Optional[str] = None
    flags: str = "[]"
    timezone: Optional[str] = None
    device_type: Optional[str] = None

    # From list response config block
    address: Optional[str] = None       # Modbus unit ID (config.address as str)
    port_number: Optional[int] = None   # config.portNumber
    baud_rate: Optional[int] = None     # config.baudRate
    com_type: Optional[str] = None      # config.comType

    # From full hardware detail (GET /Hardware/{id})
    ip_address: Optional[str] = None    # top-level address (IP string or "0")
    port: Optional[int] = None          # top-level port
    port_mode: Optional[str] = None     # top-level portMode
    gateway_id: Optional[str] = Field(default=None, index=True)
    driver_name: Optional[str] = None
    driver_settings_json: str = "{}"
    register_groups_json: str = "[]"
    is_virtual_device: bool = False
    # Extracted from driver.settings for quick access without JSON parsing
    modbus_unit_id: Optional[str] = None   # driver.settings.UnitID
    tcp_port: Optional[str] = None         # driver.settings.TCPPort

    raw_json: str = "{}"
    last_synced: Optional[datetime] = None

    def flags_list(self) -> list[str]:
        try:
            return json.loads(self.flags)
        except Exception:
            return []

    def driver_settings(self) -> dict:
        try:
            return json.loads(self.driver_settings_json)
        except Exception:
            return {}


class Gateway(SQLModel, table=True):
    __tablename__ = "gateways"

    gateway_id: str = Field(primary_key=True)
    site_id: int = Field(foreign_key="sites.site_id", index=True)
    hardware_id: Optional[int] = Field(default=None, foreign_key="hardware.id")
    name: str = ""
    parameters_json: str = "[]"
    device_configs_json: str = "{}"
    last_synced: Optional[datetime] = None

    def parameters(self) -> list[dict]:
        try:
            return json.loads(self.parameters_json)
        except Exception:
            return []


class MigrationJob(SQLModel, table=True):
    __tablename__ = "migration_jobs"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = ""
    status: str = JOB_STATUS_PENDING  # pending/running/done/error/cancelled/emailed
    # JSON array of site IDs selected for this job
    site_ids_json: str = "[]"
    include_virtual: bool = True
    include_data_devices: bool = True
    # Populated after run completes
    csv_path: Optional[str] = None
    sites_synced: int = 0
    devices_found: int = 0
    virtual_skipped: int = 0
    registers_captured: int = 0
    error_count: int = 0
    error_detail: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    emailed_at: Optional[datetime] = None

    def site_ids(self) -> list[int]:
        try:
            return json.loads(self.site_ids_json)
        except Exception:
            return []


class DiscoveryResult(SQLModel, table=True):
    __tablename__ = "discovery_results"

    site_id: int = Field(primary_key=True)
    site_name: str = ""
    tcp_count: int = 0
    rtu_count: int = 0
    unknown_count: int = 0
    last_scanned: Optional[datetime] = None
