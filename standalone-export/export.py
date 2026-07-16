"""
AlsoEnergy Asset Owner Export Tool — standalone CLI
Fetches all sites + hardware from the AlsoEnergy API and writes a 31-column CSV.
Results are cached in a local SQLite database so subsequent runs are instant.
Use --refresh to force a full re-sync from the API.
"""

import asyncio
import base64
import csv
import io
import json
import logging
import os
import random
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path
from typing import Any, Optional

try:
    import httpx
except ImportError:
    print("ERROR: httpx is not installed. Please run the launch script (run.bat / run.sh) "
          "instead of calling python export.py directly.")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

TOOL_VERSION = "0.1.0"
BASE_URL = os.environ.get("ALSOENERGY_BASE_URL", "https://api.alsoenergy.com")
SCRIPT_DIR = Path(__file__).parent
CACHE_PATH = SCRIPT_DIR / "cache" / "export.db"

# ---------------------------------------------------------------------------
# Timezone mapping
# ---------------------------------------------------------------------------

_TZ_MAP: dict[str, str] = {
    "(UTC-05:00) Eastern Time (US & Canada)": "America/New_York",
    "(UTC-04:00) Eastern Time (US & Canada)": "America/New_York",
    "(UTC-06:00) Central Time (US & Canada)": "America/Chicago",
    "(UTC-05:00) Central Time (US & Canada)": "America/Chicago",
    "(UTC-07:00) Mountain Time (US & Canada)": "America/Denver",
    "(UTC-06:00) Mountain Time (US & Canada)": "America/Denver",
    "(UTC-07:00) Arizona": "America/Phoenix",
    "(UTC-08:00) Pacific Time (US & Canada)": "America/Los_Angeles",
    "(UTC-07:00) Pacific Time (US & Canada)": "America/Los_Angeles",
    "(UTC-09:00) Alaska": "America/Anchorage",
    "(UTC-10:00) Hawaii": "Pacific/Honolulu",
    "(UTC-04:00) Atlantic Time (Canada)": "America/Halifax",
    "(UTC-03:30) Newfoundland": "America/St_Johns",
    "(UTC) Greenwich Mean Time : Dublin, Edinburgh, Lisbon, London": "Europe/London",
    "(UTC) UTC": "UTC",
    "(UTC+00:00) UTC": "UTC",
    "Eastern Standard Time": "America/New_York",
    "Central Standard Time": "America/Chicago",
    "Mountain Standard Time": "America/Denver",
    "US Mountain Standard Time": "America/Phoenix",
    "Pacific Standard Time": "America/Los_Angeles",
    "Alaskan Standard Time": "America/Anchorage",
    "Hawaiian Standard Time": "Pacific/Honolulu",
    "Atlantic Standard Time": "America/Halifax",
    "Newfoundland Standard Time": "America/St_Johns",
    "GMT Standard Time": "Europe/London",
    "UTC": "UTC",
}


def resolve_iana(display_name: Optional[str]) -> str:
    if not display_name:
        return ""
    s = display_name.strip()
    if "/" in s and " " not in s:
        return s
    if s in _TZ_MAP:
        return _TZ_MAP[s]
    if s.startswith("LEGACY:"):
        inner = s[7:].strip()
        return _TZ_MAP.get(inner, s)
    log.warning("unmapped timezone displayName: %r", s)
    return f"LEGACY:{s}"


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class SiteData:
    site_id: int
    site_name: str = ""
    timezone: Optional[str] = None


@dataclass
class HardwareData:
    id: int
    site_id: int
    name: str = ""
    string_id: Optional[str] = None
    function_code: Optional[str] = None
    serial_number: Optional[str] = None
    flags: list = field(default_factory=list)
    device_type: Optional[str] = None
    address: Optional[str] = None
    port_number: Optional[int] = None
    baud_rate: Optional[int] = None
    com_type: Optional[str] = None
    ip_address: Optional[str] = None
    address_source: Optional[str] = None
    gateway_id: Optional[str] = None
    driver_name: Optional[str] = None
    driver_settings: dict = field(default_factory=dict)
    register_groups: list = field(default_factory=list)
    is_virtual_device: bool = False
    modbus_unit_id: Optional[str] = None
    tcp_port: Optional[str] = None


@dataclass
class GatewayData:
    gateway_id: str
    site_id: int
    name: str = ""


# ---------------------------------------------------------------------------
# SQLite cache
# ---------------------------------------------------------------------------

class Cache:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sites (
                site_id     INTEGER PRIMARY KEY,
                site_name   TEXT NOT NULL DEFAULT '',
                timezone    TEXT,
                last_synced TEXT
            );

            CREATE TABLE IF NOT EXISTS hardware (
                id                  INTEGER PRIMARY KEY,
                site_id             INTEGER NOT NULL,
                name                TEXT NOT NULL DEFAULT '',
                string_id           TEXT,
                function_code       TEXT,
                serial_number       TEXT,
                flags_json          TEXT NOT NULL DEFAULT '[]',
                device_type         TEXT,
                address             TEXT,
                port_number         INTEGER,
                baud_rate           INTEGER,
                com_type            TEXT,
                ip_address          TEXT,
                address_source      TEXT,
                gateway_id          TEXT,
                driver_name         TEXT,
                driver_settings_json TEXT NOT NULL DEFAULT '{}',
                register_groups_json TEXT NOT NULL DEFAULT '[]',
                is_virtual_device   INTEGER NOT NULL DEFAULT 0,
                modbus_unit_id      TEXT,
                tcp_port            TEXT,
                last_synced         TEXT
            );

            CREATE TABLE IF NOT EXISTS gateways (
                gateway_id  TEXT PRIMARY KEY,
                site_id     INTEGER NOT NULL,
                name        TEXT NOT NULL DEFAULT '',
                last_synced TEXT
            );
        """)
        self._conn.commit()
        # Additive migration for pre-existing cache files created before this column existed.
        try:
            self._conn.execute("ALTER TABLE hardware ADD COLUMN address_source TEXT")
            self._conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists

    def is_populated(self) -> bool:
        row = self._conn.execute("SELECT COUNT(*) FROM sites").fetchone()
        return row[0] > 0

    def clear(self) -> None:
        self._conn.executescript("DELETE FROM hardware; DELETE FROM gateways; DELETE FROM sites;")
        self._conn.commit()
        log.info("Cache cleared.")

    def upsert_site(self, s: SiteData) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute("""
            INSERT INTO sites (site_id, site_name, timezone, last_synced)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(site_id) DO UPDATE SET
                site_name=excluded.site_name,
                timezone=excluded.timezone,
                last_synced=excluded.last_synced
        """, (s.site_id, s.site_name, s.timezone, now))

    def upsert_hardware(self, hw: HardwareData) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute("""
            INSERT INTO hardware (
                id, site_id, name, string_id, function_code, serial_number,
                flags_json, device_type, address, port_number, baud_rate, com_type,
                ip_address, address_source, gateway_id, driver_name, driver_settings_json,
                register_groups_json, is_virtual_device, modbus_unit_id, tcp_port, last_synced
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                site_id=excluded.site_id, name=excluded.name,
                string_id=excluded.string_id, function_code=excluded.function_code,
                serial_number=excluded.serial_number, flags_json=excluded.flags_json,
                device_type=excluded.device_type, address=excluded.address,
                port_number=excluded.port_number, baud_rate=excluded.baud_rate,
                com_type=excluded.com_type, ip_address=excluded.ip_address,
                address_source=excluded.address_source,
                gateway_id=excluded.gateway_id, driver_name=excluded.driver_name,
                driver_settings_json=excluded.driver_settings_json,
                register_groups_json=excluded.register_groups_json,
                is_virtual_device=excluded.is_virtual_device,
                modbus_unit_id=excluded.modbus_unit_id, tcp_port=excluded.tcp_port,
                last_synced=excluded.last_synced
        """, (
            hw.id, hw.site_id, hw.name, hw.string_id, hw.function_code, hw.serial_number,
            json.dumps(hw.flags), hw.device_type, hw.address, hw.port_number, hw.baud_rate,
            hw.com_type, hw.ip_address, hw.address_source, hw.gateway_id, hw.driver_name,
            json.dumps(hw.driver_settings), json.dumps(hw.register_groups),
            int(hw.is_virtual_device), hw.modbus_unit_id, hw.tcp_port, now,
        ))

    def upsert_gateway(self, gw: GatewayData) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute("""
            INSERT INTO gateways (gateway_id, site_id, name, last_synced)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(gateway_id) DO UPDATE SET
                site_id=excluded.site_id, name=excluded.name, last_synced=excluded.last_synced
        """, (gw.gateway_id, gw.site_id, gw.name, now))

    def commit(self) -> None:
        self._conn.commit()

    def load_sites(self, site_ids: Optional[list[int]] = None) -> list[SiteData]:
        if site_ids:
            placeholders = ",".join("?" * len(site_ids))
            rows = self._conn.execute(
                f"SELECT * FROM sites WHERE site_id IN ({placeholders})", site_ids
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM sites").fetchall()
        return [SiteData(site_id=r["site_id"], site_name=r["site_name"], timezone=r["timezone"])
                for r in rows]

    def load_hardware(self, site_id: int) -> list[HardwareData]:
        rows = self._conn.execute(
            "SELECT * FROM hardware WHERE site_id = ?", (site_id,)
        ).fetchall()
        result = []
        for r in rows:
            hw = HardwareData(
                id=r["id"], site_id=r["site_id"], name=r["name"],
                string_id=r["string_id"], function_code=r["function_code"],
                serial_number=r["serial_number"],
                flags=json.loads(r["flags_json"] or "[]"),
                device_type=r["device_type"], address=r["address"],
                port_number=r["port_number"], baud_rate=r["baud_rate"],
                com_type=r["com_type"], ip_address=r["ip_address"],
                address_source=r["address_source"],
                gateway_id=r["gateway_id"], driver_name=r["driver_name"],
                driver_settings=json.loads(r["driver_settings_json"] or "{}"),
                register_groups=json.loads(r["register_groups_json"] or "[]"),
                is_virtual_device=bool(r["is_virtual_device"]),
                modbus_unit_id=r["modbus_unit_id"], tcp_port=r["tcp_port"],
            )
            result.append(hw)
        return result

    def load_gateways(self) -> dict[str, GatewayData]:
        rows = self._conn.execute("SELECT * FROM gateways").fetchall()
        return {r["gateway_id"]: GatewayData(
            gateway_id=r["gateway_id"], site_id=r["site_id"], name=r["name"]
        ) for r in rows}

    def last_synced(self) -> Optional[str]:
        row = self._conn.execute(
            "SELECT MIN(last_synced) FROM sites WHERE last_synced IS NOT NULL"
        ).fetchone()
        return row[0] if row else None

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Auth + API client
# ---------------------------------------------------------------------------

class AuthError(Exception):
    pass


class AlsoEnergyClient:
    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password
        self._access_token: Optional[str] = None
        self._expires_at: float = 0.0
        self._http = httpx.AsyncClient(base_url=BASE_URL, timeout=30.0)

    async def authenticate(self) -> None:
        resp = await self._http.post("/Auth/token", data={
            "grant_type": "password",
            "username": self._username,
            "password": self._password,
        })
        resp.raise_for_status()
        payload = resp.json()
        self._access_token = payload["access_token"]
        self._expires_at = self._jwt_exp(payload["access_token"])

    @staticmethod
    def _jwt_exp(token: str) -> float:
        try:
            part = token.split(".")[1]
            part += "=" * (-len(part) % 4)
            claims = json.loads(base64.urlsafe_b64decode(part))
            return time.monotonic() + (claims["exp"] - time.time())
        except Exception:
            return time.monotonic() + 900

    def _needs_refresh(self) -> bool:
        return time.monotonic() >= self._expires_at - 60

    async def _ensure_token(self) -> None:
        if self._access_token is None or self._needs_refresh():
            await self.authenticate()

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        await self._ensure_token()
        last_exc: Optional[Exception] = None
        for attempt in range(5):
            headers = {"Authorization": f"Bearer {self._access_token}"}
            try:
                resp = await self._http.request(method, path, headers=headers, **kwargs)
            except httpx.TransportError as exc:
                last_exc = exc
                await asyncio.sleep(min(2 ** attempt, 8) + random.uniform(0, 0.5))
                continue
            if resp.status_code == 401:
                await self.authenticate()
                headers = {"Authorization": f"Bearer {self._access_token}"}
                resp = await self._http.request(method, path, headers=headers, **kwargs)
                if resp.status_code == 401:
                    raise AuthError("Authentication failed after token refresh")
            if resp.status_code == 429 or resp.status_code >= 500:
                last_exc = httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}", request=resp.request, response=resp
                )
                await asyncio.sleep(min(2 ** attempt, 8) + random.uniform(0, 0.5))
                continue
            resp.raise_for_status()
            return resp.json()
        raise last_exc or RuntimeError("Request failed after retries")

    async def get_sites(self) -> list[dict]:
        page, size = 1, 100
        results: list[dict] = []
        while True:
            resp = await self._request("GET", "/Sites", params={"page": page, "pageSize": size})
            if isinstance(resp, list):
                return resp
            items = resp.get("items", [])
            results.extend(items)
            if len(results) >= resp.get("totalCount", len(results)) or not items:
                break
            page += 1
        return results

    async def get_site(self, site_id: int) -> dict:
        return await self._request("GET", f"/Sites/{site_id}")

    async def get_site_hardware(self, site_id: int) -> dict:
        return await self._request("GET", f"/Sites/{site_id}/Hardware", params={
            "includeArchivedFields": "true",
            "includeDeviceConfig": "true",
            "includeSummaryFields": "true",
            "includeDataNameFields": "true",
        })

    async def get_hardware(self, hw_id: int) -> dict:
        return await self._request("GET", f"/Hardware/{hw_id}")

    async def get_gateway_devices_config(self, gateway_id: str) -> dict:
        return await self._request("GET", f"/Gateways/{gateway_id}/Devices/Config",
                                   params={"withGatewayCommands": "true"})

    async def close(self) -> None:
        await self._http.aclose()


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_site(raw: dict) -> SiteData:
    tz_field = raw.get("timeZone")
    if isinstance(tz_field, dict):
        display = tz_field.get("displayName") or tz_field.get("name") or ""
        tz_str = resolve_iana(display) or None
    else:
        tz_str = resolve_iana(tz_field) if tz_field else tz_field
    return SiteData(
        site_id=raw["siteId"],
        site_name=raw.get("name") or raw.get("siteName", ""),
        timezone=tz_str,
    )


import re
import socket
import struct

_IP_OCTET = r"(?:25[0-5]|2[0-4]\d|1?\d?\d)"
_IP_RE = re.compile(rf"\b{_IP_OCTET}(?:\.{_IP_OCTET}){{3}}\b")


def _looks_like_ip(s: str) -> bool:
    """True if the entire string is a valid dotted-decimal IPv4 address."""
    return bool(_IP_RE.fullmatch(s.strip()))


def _extract_ip(text: str) -> Optional[str]:
    """Find the first valid dotted-decimal IPv4 substring inside an arbitrary
    string (e.g. a URL like 'https://166.164.242.83:8080'). Returns None if
    nothing octet-valid is found — never fabricates a match."""
    if not isinstance(text, str):
        return None
    m = _IP_RE.search(text)
    return m.group(0) if m else None


def _le_decode_candidate(int_val: int) -> str:
    """Little-endian decode of a packed-int address, for diagnostics only —
    never assigned to ip_address until confirmed across a broad live sample."""
    return socket.inet_ntoa(struct.pack("<I", int_val & 0xFFFFFFFF))


# Ordered list of driver.settings keys known to embed a usable address for
# drivers that don't populate the top-level detail.address. Confirmed shapes
# so far:
#   - SMA WebBox/SCCom: real IP as a bare dotted string under "SerialNumber"
#   - Axis Camera: real IP embedded in a URL under "accessURL"/"AccessURL"
# Extend only once a real device has proven a new key — do not guess.
# KEEP IN SYNC WITH backend/app/sync.py::_FALLBACK_ADDRESS_KEYS
_FALLBACK_ADDRESS_KEYS = ["SerialNumber", "AccessURL", "accessURL"]


def _find_fallback_address(driver_settings: dict) -> tuple[Optional[str], Optional[str]]:
    """Scan known driver.settings keys for an embedded IP. Returns
    (ip, source_tag) or (None, None). Only ever returns a value that passed
    IP-shape validation — never returns an unvalidated raw string.
    KEEP IN SYNC WITH backend/app/sync.py::_find_fallback_address"""
    for key in _FALLBACK_ADDRESS_KEYS:
        val = driver_settings.get(key)
        if not isinstance(val, str) or not val.strip():
            continue
        if _looks_like_ip(val):
            return val.strip(), f"driver_settings.{key}"
        candidate = _extract_ip(val)
        if candidate:
            return candidate, f"driver_settings.{key}"
    return None, None


def _normalize_address(value) -> tuple[Optional[str], Optional[str]]:
    """Return (ip, source_tag) for a top-level detail.address value.

    - blank/zero -> (None, None)
    - dotted string -> (ip, "confirmed")
    - non-blank string that ISN'T a valid dotted IP -> (None, None); never
      guess at malformed/unexpected data
    - integer / integer-looking -> (None, "int_decoded_le_unconfirmed"); the
      little-endian-decoded value is available via _le_decode_candidate() for
      diagnostics only, and is NOT assigned to ip_address (see plan notes —
      circumstantial evidence only, not proven across a broad enough sample).
    KEEP IN SYNC WITH backend/app/sync.py::_normalize_ip"""
    if value in (None, "", "0", 0):
        return None, None
    if isinstance(value, str):
        if _looks_like_ip(value):
            return value, "confirmed"
        return None, None
    try:
        int_val = int(value)
    except (ValueError, TypeError):
        return None, None
    if int_val == 0:
        return None, None
    return None, "int_decoded_le_unconfirmed"


def _parse_hardware(site_id: int, raw: dict) -> HardwareData:
    cfg = raw.get("config") or raw.get("deviceConfig") or {}
    flags_raw = raw.get("flags") or []
    flags = flags_raw if isinstance(flags_raw, list) else [f for f, v in flags_raw.items() if v is True]
    addr = cfg.get("address")
    return HardwareData(
        id=raw.get("id") or raw.get("hardwareId"),
        site_id=site_id,
        name=raw.get("name") or raw.get("hardwareName", ""),
        string_id=raw.get("stringId"),
        function_code=raw.get("functionCode"),
        serial_number=cfg.get("serialNumber") or raw.get("serialNumber"),
        flags=flags,
        device_type=cfg.get("deviceType"),
        address=str(addr) if addr is not None else None,
        port_number=cfg.get("portNumber"),
        baud_rate=cfg.get("baudRate"),
        com_type=cfg.get("comType"),
    )


def _enrich_hardware(hw: HardwareData, detail: dict) -> None:
    cfg = detail.get("config") or {}
    driver = detail.get("driver") or {}
    flags_raw = detail.get("flags") or []
    flags = flags_raw if isinstance(flags_raw, list) else [f for f, v in flags_raw.items() if v is True]

    ip_addr = detail.get("address")
    port_mode = detail.get("portMode")
    driver_settings = driver.get("settings") or {}

    addr_zero = ip_addr in (None, "0", 0, "")
    hw.is_virtual_device = (
        addr_zero
        and port_mode == "Unknown"
        and hw.function_code not in ("GW", "DA")
        and cfg.get("comType") == "Unknown"
        and (cfg.get("portNumber") or 0) == 0
    )

    # Trust the top-level detail address directly — driver.settings.TCPPort isn't
    # populated by every driver (SMA WebBox, Axis Camera, etc. omit it even when
    # the device has a real network address), so it can't gate whether we keep it.
    # Validate the value actually looks like an IP rather than assigning it blind;
    # if it doesn't resolve, fall back to known driver-settings keys (only when
    # the device isn't already known-virtual).
    ip, source = _normalize_address(ip_addr)
    if ip is None and not hw.is_virtual_device:
        fallback_ip, fallback_source = _find_fallback_address(driver_settings)
        if fallback_ip is not None:
            ip, source = fallback_ip, fallback_source
    hw.ip_address = ip
    hw.address_source = source
    hw.gateway_id = detail.get("gatewayId")
    hw.driver_name = driver.get("name")
    hw.driver_settings = driver_settings
    hw.register_groups = detail.get("registerGroups") or []
    hw.flags = flags
    hw.modbus_unit_id = str(driver_settings["UnitID"]) if "UnitID" in driver_settings else None
    hw.tcp_port = str(driver_settings["TCPPort"]) if "TCPPort" in driver_settings else None


# ---------------------------------------------------------------------------
# CSV generation
# ---------------------------------------------------------------------------

COLUMNS = [
    "migration_job_name", "site_id", "site_name", "site_timezone",
    "gateway_id", "gateway_name", "channel_mode", "channel_host",
    "channel_tcp_port", "channel_serial_port", "channel_baud_rate",
    "device_id", "device_name", "device_string_id", "device_function_code",
    "device_type", "device_serial_number", "modbus_unit_id", "is_enabled",
    "is_virtual_device", "driver_name", "register_group", "tag_name",
    "tag_modbus_address", "tag_raw_value", "tag_value", "tag_is_archived",
    "tag_data_type", "archived_field_name", "generated_at", "tool_version",
]

_NAN_VALS = {"nan", "NaN", "NAN", "infinity", "Infinity", "INFINITY", "-infinity", "-Infinity"}


def _bool(v) -> str:
    return "true" if v else "false"


def _clean(v) -> str:
    s = str(v).strip() if v is not None else ""
    return "" if s in _NAN_VALS else s


def _channel_mode(hw: HardwareData) -> str:
    """A validated ip_address wins even when comType also reads as a serial
    type — confirmed in the wild (Nexus meters, ABB inverter modules sharing
    one gateway IP with per-module unit IDs) where comType is a stale/generic
    label but the device is genuinely polled over TCP."""
    if hw.ip_address:
        return "TCP"
    if hw.com_type in ("Rs485_2Wire", "Rs485_4Wire", "Rs232", "Rs485"):
        return "RTU"
    return "UNKNOWN"


def _modbus_unit_id(hw: HardwareData, channel_mode: str) -> str:
    if channel_mode == "TCP":
        return hw.modbus_unit_id or ""
    if channel_mode == "RTU":
        return hw.address or ""
    return ""


def _device_rows(job_name: str, site: SiteData, hw: HardwareData,
                 gateway: Optional[GatewayData], generated_at: str) -> list[dict]:
    is_enabled = "IsEnabled" in hw.flags
    channel_mode = _channel_mode(hw)
    is_tcp = channel_mode == "TCP"
    is_serial = channel_mode == "RTU"

    base = {
        "migration_job_name": job_name,
        "site_id": str(hw.site_id),
        "site_name": site.site_name or "",
        "site_timezone": resolve_iana(site.timezone) if site.timezone else "",
        "gateway_id": hw.gateway_id or "",
        "gateway_name": gateway.name if gateway else "",
        "channel_mode": channel_mode,
        "channel_host": hw.ip_address or "" if is_tcp else "",
        "channel_tcp_port": hw.tcp_port or "" if is_tcp else "",
        "channel_serial_port": str(hw.port_number) if is_serial and hw.port_number else "",
        "channel_baud_rate": str(hw.baud_rate) if is_serial and hw.baud_rate else "",
        "device_id": str(hw.id),
        "device_name": hw.name or "",
        "device_string_id": hw.string_id or "",
        "device_function_code": hw.function_code or "",
        "device_type": hw.device_type or "",
        "device_serial_number": hw.serial_number or "",
        "modbus_unit_id": _modbus_unit_id(hw, channel_mode),
        "is_enabled": _bool(is_enabled),
        "is_virtual_device": _bool(hw.is_virtual_device),
        "driver_name": hw.driver_name or "",
        "register_group": "",
        "tag_name": "",
        "tag_modbus_address": "",
        "tag_raw_value": "",
        "tag_value": "",
        "tag_is_archived": "",
        "tag_data_type": "",
        "archived_field_name": "",
        "generated_at": generated_at,
        "tool_version": TOOL_VERSION,
    }

    rows: list[dict] = []
    if hw.register_groups:
        for group in hw.register_groups:
            group_name = group.get("name") or ""
            for reg in (group.get("registers") or []):
                data_name = reg.get("dataName") or ""
                reg_name = reg.get("name") or ""
                tag_name = data_name or reg_name
                is_archived = bool(reg.get("isArchived", False))
                arch = (data_name or reg_name) if is_archived else ""
                row = dict(base)
                row["register_group"] = group_name
                row["tag_name"] = tag_name
                row["tag_modbus_address"] = _clean(reg.get("address") or "")
                row["tag_raw_value"] = _clean(reg.get("rawValue"))
                row["tag_value"] = _clean(reg.get("value"))
                row["tag_is_archived"] = _bool(is_archived)
                row["archived_field_name"] = arch
                rows.append(row)
    else:
        rows.append(dict(base))

    return rows


def generate_csv(
    cache: Cache,
    site_ids: Optional[list[int]],
    job_name: str = "export",
    include_virtual: bool = True,
    include_data_devices: bool = True,
) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _DATA_DEVICE_CODES = {"DA", "CE", "RD", "GW"}

    sites = cache.load_sites(site_ids)
    gateways = cache.load_gateways()

    buf = io.StringIO()
    buf.write("﻿")  # UTF-8 BOM for Excel
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\r\n")
    writer.writeheader()

    for site in sites:
        for hw in cache.load_hardware(site.site_id):
            if not include_virtual and hw.is_virtual_device:
                continue
            if not include_data_devices and hw.function_code in _DATA_DEVICE_CODES:
                continue
            gateway = gateways.get(hw.gateway_id) if hw.gateway_id else None
            for row in _device_rows(job_name, site, hw, gateway, generated_at):
                writer.writerow({k: _clean(v) for k, v in row.items()})

    return buf.getvalue()


def summarize_unresolved(cache: Cache, site_ids: Optional[list[int]]) -> dict[str, int]:
    """Count non-virtual devices whose channel_mode is still UNKNOWN, grouped
    by driver_name, so gaps in address resolution surface automatically
    instead of requiring manual CSV inspection."""
    counts: dict[str, int] = {}
    for site in cache.load_sites(site_ids):
        for hw in cache.load_hardware(site.site_id):
            if hw.is_virtual_device:
                continue
            if _channel_mode(hw) != "UNKNOWN":
                continue
            key = hw.driver_name or "(unknown driver)"
            counts[key] = counts.get(key, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Sync — fetch from API and save to cache
# ---------------------------------------------------------------------------

async def sync_site(
    client: AlsoEnergyClient,
    cache: Cache,
    site_raw: dict,
    sem: asyncio.Semaphore,
) -> int:
    """Sync one site's hardware into the cache. Returns device count."""
    site_id = site_raw["siteId"]

    async with sem:
        try:
            detail = await client.get_site(site_id)
            site = _parse_site(detail)
        except Exception:
            site = _parse_site(site_raw)
        cache.upsert_site(site)

        try:
            hw_resp = await client.get_site_hardware(site_id)
            items = hw_resp if isinstance(hw_resp, list) else (
                hw_resp.get("hardware") or hw_resp.get("items") or []
            )
        except Exception as exc:
            log.warning("  site %s: hardware list failed: %s", site_id, exc)
            cache.commit()
            return 0

    hw_map = {(raw.get("id") or raw.get("hardwareId")): _parse_hardware(site_id, raw)
              for raw in items}

    detail_sem = asyncio.Semaphore(5)

    async def _enrich(hw_id: int) -> None:
        async with detail_sem:
            try:
                detail = await client.get_hardware(hw_id)
                _enrich_hardware(hw_map[hw_id], detail)
            except Exception as exc:
                log.debug("  hw %s enrich failed: %s", hw_id, exc)

    await asyncio.gather(*[_enrich(hw_id) for hw_id in hw_map], return_exceptions=True)

    for hw in hw_map.values():
        cache.upsert_hardware(hw)

    # Gateway configs
    gateway_ids: dict[str, str] = {}
    for hw in hw_map.values():
        if hw.gateway_id and hw.gateway_id not in gateway_ids:
            gw_name = hw.gateway_id
            for candidate in hw_map.values():
                if candidate.function_code == "GW" and candidate.gateway_id == hw.gateway_id:
                    gw_name = candidate.name
                    break
            gateway_ids[hw.gateway_id] = gw_name

    async with sem:
        async def _fetch_gw(gw_id: str, gw_name: str) -> None:
            try:
                await client.get_gateway_devices_config(gw_id)
            except Exception:
                pass
            cache.upsert_gateway(GatewayData(gateway_id=gw_id, site_id=site_id, name=gw_name))

        await asyncio.gather(*[_fetch_gw(gid, gname) for gid, gname in gateway_ids.items()])

    cache.commit()
    return len(hw_map)


async def sync_all(
    username: str,
    password: str,
    cache: Cache,
    site_filter: Optional[list[int]] = None,
) -> None:
    client = AlsoEnergyClient(username, password)
    try:
        log.info("Authenticating...")
        await client.authenticate()

        log.info("Fetching site list...")
        sites_raw = await client.get_sites()
        if site_filter:
            id_set = set(site_filter)
            sites_raw = [s for s in sites_raw if s.get("siteId") in id_set]

        total = len(sites_raw)
        log.info("Syncing %d site(s)...", total)

        sem = asyncio.Semaphore(3)
        results = await asyncio.gather(
            *[sync_site(client, cache, raw, sem) for raw in sites_raw],
            return_exceptions=True,
        )

        for i, result in enumerate(results):
            site_id = sites_raw[i]["siteId"]
            site_name = sites_raw[i].get("siteName") or sites_raw[i].get("name") or str(site_id)
            if isinstance(result, Exception):
                log.warning("  site %s (%s) failed: %s", site_id, site_name, result)
            else:
                log.info("  [%d/%d] %s — %d device(s)", i + 1, total, site_name, result)

        log.info("Sync complete. Data saved to cache.")
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Credential resolution
# ---------------------------------------------------------------------------

def get_credentials() -> tuple[str, str]:
    username = os.environ.get("ALSOENERGY_USERNAME", "").strip()
    password = os.environ.get("ALSOENERGY_PASSWORD", "").strip()
    if username and password:
        return username, password

    print("\nAlsoEnergy credentials not found in .env file.")
    print("Enter your credentials below (they are NOT saved anywhere):\n")
    if not username:
        username = input("AlsoEnergy username: ").strip()
    if not password:
        password = getpass("AlsoEnergy password: ").strip()

    if not username or not password:
        print("ERROR: Username and password are required.")
        sys.exit(1)

    return username, password


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Export AlsoEnergy asset data to CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Export all sites (uses cache if available):
    python export.py

  Force a full re-sync from the API first:
    python export.py --refresh

  Export with a custom job name:
    python export.py --job-name "Q2-Migration"

  Export specific sites only:
    python export.py --sites 12345 67890
        """,
    )
    parser.add_argument("--refresh", action="store_true",
                        help="Re-sync all data from the API before exporting")
    parser.add_argument("--sync-only", action="store_true",
                        help="Sync data to cache but do not generate a CSV")
    parser.add_argument("--job-name", default="export",
                        help="Label embedded in every CSV row (default: export)")
    parser.add_argument("--output-dir", default="exports",
                        help="Directory to write the CSV file (default: exports/)")
    parser.add_argument("--sites", nargs="+", type=int, metavar="SITE_ID",
                        help="Only include these site IDs (applies to both sync and export)")
    parser.add_argument("--no-virtual", action="store_true",
                        help="Exclude virtual devices from the export")
    parser.add_argument("--no-data-devices", action="store_true",
                        help="Exclude data/gateway devices (function codes DA/CE/RD/GW)")
    args = parser.parse_args()

    cache = Cache(CACHE_PATH)

    needs_sync = args.refresh or not cache.is_populated()

    if needs_sync:
        if args.refresh:
            cache.clear()
        username, password = get_credentials()
        asyncio.run(sync_all(username, password, cache, site_filter=args.sites))
    else:
        last = cache.last_synced()
        log.info("Using cached data (last synced: %s). Run with --refresh to update.", last)

    if args.sync_only:
        cache.close()
        return

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = SCRIPT_DIR / output_dir

    log.info("Generating CSV...")
    csv_content = generate_csv(
        cache=cache,
        site_ids=args.sites,
        job_name=args.job_name,
        include_virtual=not args.no_virtual,
        include_data_devices=not args.no_data_devices,
    )

    unresolved = summarize_unresolved(cache, args.sites)
    if unresolved:
        log.warning("Unresolved (non-virtual, still UNKNOWN) devices by driver:")
        for driver_name, n in sorted(unresolved.items(), key=lambda kv: -kv[1]):
            log.warning("  %-50s %d", driver_name, n)
    else:
        log.info("No unresolved non-virtual devices — all resolved to TCP/RTU.")

    cache.close()

    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_path = output_dir / f"{args.job_name}_{date_str}.csv"
    out_path.write_text(csv_content, encoding="utf-8-sig")

    print(f"\nDone! CSV written to:\n  {out_path}\n")


if __name__ == "__main__":
    main()
