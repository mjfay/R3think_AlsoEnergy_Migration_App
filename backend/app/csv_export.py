"""
CSV export — one row per register (or per archived field, or one stub row).
Follows the 31-column spec from the migration addendum exactly.
"""
import csv
import io
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import Gateway, Hardware, Site
from app.timezones import resolve_iana


@dataclass
class ExportStats:
    """Diagnostics accumulated while generating a CSV, surfaced separately
    from the 31-column deliverable (which stays spec-exact)."""
    unresolved_by_driver: dict[str, int] = field(default_factory=dict)

TOOL_VERSION = "0.2.0"

# Column order matches the spec exactly
COLUMNS = [
    "migration_job_name",
    "site_id",
    "site_name",
    "site_timezone",
    "gateway_id",
    "gateway_name",
    "channel_mode",
    "channel_host",
    "channel_tcp_port",
    "channel_serial_port",
    "channel_baud_rate",
    "device_id",
    "device_name",
    "device_string_id",
    "device_function_code",
    "device_type",
    "device_serial_number",
    "modbus_unit_id",
    "is_enabled",
    "is_virtual_device",
    "driver_name",
    "register_group",
    "tag_name",
    "tag_modbus_address",
    "tag_raw_value",
    "tag_value",
    "tag_is_archived",
    "tag_data_type",
    "archived_field_name",
    "generated_at",
    "tool_version",
]


def _bool(v) -> str:
    return "true" if v else "false"


def _channel_mode(hw: Hardware) -> str:
    """Classify channel as TCP/RTU/UNKNOWN.

    A validated ip_address wins even when comType also reads as a serial type —
    confirmed in the wild across many devices (Nexus meters, ABB inverter
    modules sharing one gateway IP with per-module unit IDs, etc.) where
    comType is a stale/generic label but the device is genuinely polled over
    TCP. Only fall back to comType-based RTU when there's no resolved address.

    comType can ALSO read "Unknown" for genuinely-serial devices — confirmed
    on South Burlington Solar's "Solectria 36kW TL V2 Inverter - 11" (AlsoEnergy's
    own UI shows Port=2/Baud=9600/Address=11, but config.comType="Unknown"), and
    ~550 similar RS-485-chained string inverters across the cached dataset
    (Solectria, Chint, Huawei, SunGrow, Delta, SolarEdge). In that case a real,
    nonzero port_number + baud_rate pair is the signal to trust. Devices that
    are genuinely unresolved (GW/DA/WS placeholders) reliably show baud_rate=0
    even when port_number is nonzero, so requiring BOTH nonzero avoids false
    positives — verified against production data before shipping this.
    """
    if hw.ip_address:
        return "TCP"
    if hw.com_type in ("Rs485_2Wire", "Rs485_4Wire", "Rs232", "Rs485"):
        return "RTU"
    if hw.port_number and hw.baud_rate:
        return "RTU"
    return "UNKNOWN"


_NAN_VALS = {"nan", "NaN", "NAN", "infinity", "Infinity", "INFINITY", "-infinity", "-Infinity"}

def _clean(v: str) -> str:
    """Strip whitespace; replace NaN/Infinity with empty string."""
    s = str(v).strip()
    return "" if s in _NAN_VALS else s


def _modbus_unit_id(hw: Hardware, channel_mode: str) -> str:
    """Return the Modbus slave/unit ID appropriate for the channel type."""
    if channel_mode == "TCP":
        return hw.modbus_unit_id or ""
    if channel_mode == "RTU":
        # config.address holds the RTU slave ID
        return hw.address or ""
    return ""


def _device_rows(
    job_name: str,
    site: Site,
    hw: Hardware,
    gateway: Gateway | None,
    generated_at: str,
) -> list[dict]:
    """Return one or more CSV row dicts for a single hardware device."""
    flags = hw.flags_list()
    is_enabled = "IsEnabled" in flags

    driver_settings = hw.driver_settings()
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

    register_groups: list[dict] = []
    try:
        register_groups = json.loads(hw.register_groups_json) or []
    except Exception:
        pass

    rows: list[dict] = []

    if register_groups:
        for group in register_groups:
            group_name = group.get("name") or ""
            registers = group.get("registers") or []
            for reg in registers:
                data_name = reg.get("dataName") or ""
                reg_name = reg.get("name") or ""
                tag_name = data_name or reg_name
                is_archived = bool(reg.get("isArchived", False))
                # archived_field_name: the dataName (or fallback name) when isArchived=true
                arch = (data_name or reg_name) if is_archived else ""
                row = dict(base)
                row["register_group"] = group_name
                row["tag_name"] = tag_name
                row["tag_modbus_address"] = _clean(reg.get("address") or "")
                row["tag_raw_value"] = _clean(reg.get("rawValue") if reg.get("rawValue") is not None else "")
                row["tag_value"] = _clean(reg.get("value") if reg.get("value") is not None else "")
                row["tag_is_archived"] = _bool(is_archived)
                row["archived_field_name"] = arch
                rows.append(row)
    else:
        rows.append(dict(base))

    return rows


_DATA_DEVICE_CODES = {"DA", "CE", "RD", "GW"}


def generate_csv(
    session: Session,
    session_id: str,
    site_ids: list[int],
    job_name: str = "export",
    include_virtual: bool = True,
    include_data_devices: bool = True,
    stats: ExportStats | None = None,
) -> str:
    """
    Generate the 31-column CSV for the given site IDs, scoped to one tenant's cached data.
    Returns the CSV as a UTF-8 string (with BOM for Excel compatibility).
    """
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Preload gateways keyed by gateway_id
    gateway_map: dict[str, Gateway] = {}
    for gw in session.exec(select(Gateway).where(Gateway.session_id == session_id)).all():
        gateway_map[gw.gateway_id] = gw

    buf = io.StringIO()
    # UTF-8 BOM
    buf.write("﻿")
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\r\n")
    writer.writeheader()

    for site_id in site_ids:
        site = session.get(Site, (session_id, site_id))
        if not site:
            continue
        devices = session.exec(
            select(Hardware).where(Hardware.session_id == session_id, Hardware.site_id == site_id)
        ).all()

        for hw in devices:
            if not include_virtual and hw.is_virtual_device:
                continue
            if not include_data_devices and hw.function_code in _DATA_DEVICE_CODES:
                continue
            gateway = gateway_map.get(hw.gateway_id) if hw.gateway_id else None
            rows = _device_rows(job_name, site, hw, gateway, generated_at)
            if stats is not None and rows and rows[0]["channel_mode"] == "UNKNOWN" and not hw.is_virtual_device:
                key = hw.driver_name or "(unknown driver)"
                stats.unresolved_by_driver[key] = stats.unresolved_by_driver.get(key, 0) + 1
            for row in rows:
                writer.writerow({k: _clean(v) for k, v in row.items()})

    return buf.getvalue()
