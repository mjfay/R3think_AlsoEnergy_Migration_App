"""Helpers that pull from the API and upsert into SQLite."""
import asyncio
import json
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.alsoenergy import client as ae
from app.models import Gateway, Hardware, Site
from app.timezones import resolve_iana


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_site(raw: dict) -> Site:
    # Detailed response uses "location" + "address" objects and "name".
    # List response only has "siteId" + "siteName".
    loc = raw.get("location") or {}
    addr = raw.get("address") or {}
    tz_field = raw.get("timeZone")
    if isinstance(tz_field, dict):
        display = tz_field.get("displayName") or tz_field.get("name") or ""
        tz_str = resolve_iana(display) or None
    else:
        tz_str = resolve_iana(tz_field) if tz_field else tz_field
    return Site(
        site_id=raw["siteId"],
        site_name=raw.get("name") or raw.get("siteName", ""),
        customer_id=raw.get("customerId"),
        timezone=tz_str,
        lat=loc.get("latitude"),
        lng=loc.get("longitude"),
        address=addr.get("address1") or addr.get("address"),
        city=addr.get("city"),
        state=addr.get("state"),
        zip_code=addr.get("zip") or addr.get("zipCode"),
        country=addr.get("country"),
        install_date=raw.get("installDate"),
        turn_on_date=raw.get("turnOnDate"),
        system_size_kw=raw.get("systemSizeKw") or (raw.get("productionData") or {}).get("systemSize"),
        raw_json=json.dumps(raw),
        last_synced=_now(),
    )


def _parse_hardware_list_item(site_id: int, raw: dict) -> Hardware:
    """Parse from /Sites/{id}/Hardware list — config block only, no detail fields."""
    cfg = raw.get("config") or raw.get("deviceConfig") or {}
    flags_raw = raw.get("flags") or []
    flags = flags_raw if isinstance(flags_raw, list) else [f for f, v in flags_raw.items() if v is True]
    addr = cfg.get("address")
    return Hardware(
        id=raw.get("id") or raw.get("hardwareId"),
        site_id=site_id,
        name=raw.get("name") or raw.get("hardwareName", ""),
        string_id=raw.get("stringId"),
        function_code=raw.get("functionCode"),
        serial_number=cfg.get("serialNumber") or raw.get("serialNumber"),
        flags=json.dumps(flags),
        timezone=raw.get("timeZone"),
        device_type=cfg.get("deviceType"),
        address=str(addr) if addr is not None else None,
        port_number=cfg.get("portNumber"),
        baud_rate=cfg.get("baudRate"),
        com_type=cfg.get("comType"),
        raw_json=json.dumps(raw),
        last_synced=_now(),
    )


def _enrich_hardware(hw: Hardware, detail: dict) -> Hardware:
    """Merge fields from GET /Hardware/{id} full detail into a Hardware row."""
    cfg = detail.get("config") or {}
    driver = detail.get("driver") or {}
    flags_raw = detail.get("flags") or []
    flags = flags_raw if isinstance(flags_raw, list) else [f for f, v in flags_raw.items() if v is True]

    ip_addr = detail.get("address")  # string IP or "0"
    port_mode = detail.get("portMode") or detail.get("portMode")

    # Virtual: address "0" or 0, portMode Unknown, and not a gateway
    addr_zero = ip_addr in (None, "0", 0, "")
    is_virtual = (
        addr_zero
        and port_mode == "Unknown"
        and hw.function_code not in ("GW", "DA")
        and cfg.get("comType") == "Unknown"
        and (cfg.get("portNumber") or 0) == 0
    )

    driver_settings = driver.get("settings") or {}
    has_tcp_port = bool(driver_settings.get("TCPPort"))
    hw.ip_address = (ip_addr if ip_addr not in (None, "0", "") else None) if has_tcp_port else None
    hw.port = detail.get("port")
    hw.port_mode = port_mode
    hw.gateway_id = detail.get("gatewayId")
    hw.driver_name = driver.get("name")
    hw.driver_settings_json = json.dumps(driver_settings)
    hw.register_groups_json = json.dumps(detail.get("registerGroups") or [])
    hw.is_virtual_device = is_virtual
    hw.flags = json.dumps(flags)
    # Extract Modbus TCP fields directly from driver.settings
    hw.modbus_unit_id = str(driver_settings["UnitID"]) if "UnitID" in driver_settings else None
    hw.tcp_port = str(driver_settings["TCPPort"]) if "TCPPort" in driver_settings else None
    # Overwrite raw_json with the richer detail response
    hw.raw_json = json.dumps(detail)
    hw.last_synced = _now()
    return hw


def _parse_gateway(gateway_id: str, site_id: int, hw_id: int | None, name: str, config_resp: dict) -> Gateway:
    items = config_resp if isinstance(config_resp, list) else config_resp.get("items", [])
    # Gateway-level parameters come from the item where deviceType == "Gateway"
    gw_params: list[dict] = []
    for item in items:
        if item.get("deviceType") == "Gateway":
            gw_params = item.get("parameters") or []
            break
    return Gateway(
        gateway_id=gateway_id,
        site_id=site_id,
        hardware_id=hw_id,
        name=name,
        parameters_json=json.dumps(gw_params),
        device_configs_json=json.dumps(items),
        last_synced=_now(),
    )


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------

def upsert_site(session: Session, site: Site) -> None:
    existing = session.get(Site, site.site_id)
    if existing:
        for k, v in site.model_dump(exclude={"site_id"}).items():
            setattr(existing, k, v)
        session.add(existing)
    else:
        session.add(site)
    session.commit()


def upsert_hardware(session: Session, hw: Hardware) -> None:
    existing = session.get(Hardware, hw.id)
    if existing:
        for k, v in hw.model_dump(exclude={"id"}).items():
            setattr(existing, k, v)
        session.add(existing)
    else:
        session.add(hw)
    session.commit()


def upsert_gateway(session: Session, gw: Gateway) -> None:
    existing = session.get(Gateway, gw.gateway_id)
    if existing:
        for k, v in gw.model_dump(exclude={"gateway_id"}).items():
            setattr(existing, k, v)
        session.add(existing)
    else:
        session.add(gw)
    session.commit()


# ---------------------------------------------------------------------------
# Sync operations
# ---------------------------------------------------------------------------

async def sync_all_sites(session: Session) -> int:
    sites_raw = await ae.get_sites()
    for raw in sites_raw:
        upsert_site(session, _parse_site(raw))
    return len(sites_raw)


async def sync_site_hardware(session: Session, site_id: int, progress_cb=None) -> int:
    """
    Full sync for one site:
    1. Pull site detail
    2. Pull hardware list
    3. Enrich each device with GET /Hardware/{id}
    4. Pull gateway configs for all unique gatewayIds
    """
    sem = asyncio.Semaphore(5)

    # 1. Site detail
    try:
        site_raw = await ae.get_site(site_id)
        upsert_site(session, _parse_site(site_raw))
    except Exception:
        pass

    # 2. Hardware list
    hw_resp = await ae.get_site_hardware(site_id)
    if isinstance(hw_resp, list):
        items = hw_resp
    else:
        items = hw_resp.get("hardware") or hw_resp.get("items") or []

    # Upsert basic rows first so they exist before enrichment
    hw_rows: dict[int, Hardware] = {}
    for raw in items:
        hw = _parse_hardware_list_item(site_id, raw)
        upsert_hardware(session, hw)
        hw_rows[hw.id] = hw

    if progress_cb:
        await progress_cb({"type": "hw_list", "siteId": site_id, "count": len(items)})

    # 3. Enrich with full detail
    async def _enrich_one(hw_id: int, idx: int):
        async with sem:
            try:
                detail = await ae.get_hardware(hw_id)
                hw = session.get(Hardware, hw_id)
                if hw:
                    _enrich_hardware(hw, detail)
                    session.add(hw)
                    session.commit()
            except Exception:
                pass
            if progress_cb:
                await progress_cb({"type": "hw_enriched", "siteId": site_id, "index": idx, "total": len(hw_rows)})

    await asyncio.gather(*[_enrich_one(hw_id, i) for i, hw_id in enumerate(hw_rows)], return_exceptions=True)

    # 4. Gateway configs — collect unique gatewayIds from now-enriched rows
    gateway_ids: dict[str, tuple[int | None, str]] = {}  # gateway_id → (hw_id, name)
    for hw_id in hw_rows:
        hw = session.get(Hardware, hw_id)
        if hw and hw.gateway_id:
            if hw.gateway_id not in gateway_ids:
                # Gateway hardware is typically functionCode GW
                gw_hw_id = None
                gw_name = hw.gateway_id
                for candidate_id, candidate_hw in hw_rows.items():
                    if candidate_hw.function_code == "GW" and candidate_hw.gateway_id == hw.gateway_id:
                        gw_hw_id = candidate_id
                        gw_name = candidate_hw.name
                        break
                gateway_ids[hw.gateway_id] = (gw_hw_id, gw_name)

    if progress_cb and gateway_ids:
        await progress_cb({"type": "gw_start", "siteId": site_id, "count": len(gateway_ids)})

    async def _sync_gateway(gw_id: str, gw_hw_id: int | None, gw_name: str):
        async with sem:
            try:
                cfg = await ae.get_gateway_devices_config(gw_id)
                gw = _parse_gateway(gw_id, site_id, gw_hw_id, gw_name, cfg)
                upsert_gateway(session, gw)
            except Exception:
                pass

    await asyncio.gather(*[
        _sync_gateway(gw_id, hw_id, name)
        for gw_id, (hw_id, name) in gateway_ids.items()
    ], return_exceptions=True)

    return len(items)


async def sync_all(
    session: Session,
    progress_cb=None,
    limit: int | None = None,
    site_ids: list[int] | None = None,
):
    """Sync sites + hardware. Pass site_ids to sync specific sites; limit to cap count."""
    sites_raw = await ae.get_sites()
    if site_ids:
        id_set = set(site_ids)
        sites_raw = [s for s in sites_raw if s.get("siteId") in id_set]
    elif limit:
        sites_raw = sites_raw[:limit]
    total = len(sites_raw)

    for raw in sites_raw:
        upsert_site(session, _parse_site(raw))

    if progress_cb:
        await progress_cb({"type": "sites_loaded", "total": total})

    outer_sem = asyncio.Semaphore(5)

    async def _sync_one(i: int, raw: dict):
        site_id = raw["siteId"]
        site_name = raw.get("siteName") or raw.get("name") or str(site_id)
        async with outer_sem:
            if progress_cb:
                await progress_cb({"type": "site_start", "index": i + 1, "total": total,
                                   "siteId": site_id, "siteName": site_name})
            try:
                count = await sync_site_hardware(session, site_id)
                if progress_cb:
                    await progress_cb({"type": "site_done", "index": i + 1, "total": total,
                                       "siteId": site_id, "siteName": site_name, "deviceCount": count})
            except Exception as exc:
                if progress_cb:
                    await progress_cb({"type": "site_error", "index": i + 1, "total": total,
                                       "siteId": site_id, "siteName": site_name, "error": str(exc)})

    await asyncio.gather(*[_sync_one(i, raw) for i, raw in enumerate(sites_raw)])

    if progress_cb:
        await progress_cb({"type": "done", "total": total})
