import argparse
import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, func, select

from app.alsoenergy import AuthError, client as ae_client
from app.credentials import delete as creds_delete
from app.credentials import has_credentials, load as creds_load, save as creds_save
from app.csv_export import TOOL_VERSION, generate_csv
from app.db import engine, get_session, init_db
from app.models import (
    DiscoveryResult, Gateway, Hardware, MigrationJob, Site,
    JOB_STATUS_CANCELLED, JOB_STATUS_DONE, JOB_STATUS_EMAILED,
    JOB_STATUS_ERROR, JOB_STATUS_PENDING, JOB_STATUS_RUNNING,
)
from app.sync import sync_all, sync_all_sites, sync_site_hardware


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Reset any jobs that were left in 'running' state by a previous crashed/killed session
    from sqlalchemy import text as _t
    with engine.connect() as _conn:
        _conn.execute(_t(
            "UPDATE migration_jobs SET status='error', "
            "error_detail='Interrupted: app was closed while job was running', "
            "completed_at=datetime('now') WHERE status='running'"
        ))
        _conn.commit()
    yield
    await ae_client.close()


app = FastAPI(title="AlsoEnergy Migration API", lifespan=lifespan)

# Allow any origin — the server only binds to 127.0.0.1 so there is no
# external access risk. Tauri webview uses tauri://localhost, dev uses
# http://localhost:5173; wildcard covers both without maintaining a list.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"ok": True, "token": ae_client.token_status}


# ---------------------------------------------------------------------------
# Credentials + auth endpoints
# ---------------------------------------------------------------------------

class CredentialPayload(BaseModel):
    username: str
    password: str

@app.get("/api/credentials/status")
async def credentials_status():
    """Returns whether credentials are stored in the OS keyring."""
    stored = has_credentials()
    return {"stored": stored}

@app.post("/api/credentials")
async def save_credentials(payload: CredentialPayload):
    """Save credentials to the OS keyring. Does NOT authenticate."""
    creds_save(payload.username, payload.password)
    return {"ok": True}

@app.delete("/api/credentials")
async def clear_credentials():
    """Remove credentials from the OS keyring and clear any active token."""
    creds_delete()
    ae_client._access_token = None
    ae_client._expires_at = 0.0
    return {"ok": True}

@app.post("/api/auth/test")
async def test_auth(payload: CredentialPayload):
    """
    Test credentials without saving them.
    Returns ok=True + tokenStatus if valid, error message if not.
    """
    try:
        await ae_client._authenticate_with(payload.username, payload.password)
        return {"ok": True, "tokenStatus": ae_client.token_status}
    except AuthError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": f"Connection failed: {exc}"}


# ---------------------------------------------------------------------------
# Sync endpoints
# ---------------------------------------------------------------------------

@app.post("/api/sync/sites")
async def sync_sites(session: Session = Depends(get_session)):
    count = await sync_all_sites(session)
    return {"synced": count}


@app.post("/api/sync/site/{site_id}")
async def sync_one_site(site_id: int, session: Session = Depends(get_session)):
    hw_count = await sync_site_hardware(session, site_id)
    return {"siteId": site_id, "devicesSynced": hw_count}


@app.get("/api/ae/sites")
async def ae_site_list():
    """Return the live site list from AlsoEnergy for the sync picker (not cached)."""
    sites_raw = await ae_client.get_sites()
    return [
        {
            "siteId": s.get("siteId"),
            "siteName": s.get("siteName") or s.get("name") or "",
            "city": s.get("city") or "",
            "state": s.get("state") or "",
            "country": s.get("country") or "",
        }
        for s in sites_raw
    ]


@app.get("/api/sync/all")
async def sync_all_sse(
    session: Session = Depends(get_session),
    limit: int = 0,
    site_ids: str = "",
):
    """SSE stream for syncing sites + hardware.
    Pass limit=N to cap at N sites, or site_ids=1,2,3 to sync specific sites.
    """
    queue: asyncio.Queue = asyncio.Queue()
    parsed_ids = [int(x) for x in site_ids.split(",") if x.strip().isdigit()] if site_ids else []

    async def progress_cb(event: dict) -> None:
        await queue.put(event)

    async def run_sync():
        try:
            await sync_all(session, progress_cb, limit=limit or None, site_ids=parsed_ids or None)
        except Exception as exc:
            await queue.put({"type": "error", "error": str(exc)})
        finally:
            await queue.put(None)  # sentinel

    async def event_stream() -> AsyncIterator[str]:
        task = asyncio.create_task(run_sync())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            task.cancel()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

@app.get("/api/sites")
def list_sites(session: Session = Depends(get_session)):
    sites = session.exec(select(Site)).all()
    result = []
    for site in sites:
        hw_count = session.exec(
            select(func.count(Hardware.id)).where(Hardware.site_id == site.site_id)
        ).one()
        result.append({
            "siteId": site.site_id,
            "siteName": site.site_name,
            "timezone": site.timezone,
            "deviceCount": hw_count,
            "lastSynced": site.last_synced.isoformat() if site.last_synced else None,
        })
    return result


@app.get("/api/sites/{site_id}")
def get_site(site_id: int, session: Session = Depends(get_session)):
    site = session.get(Site, site_id)
    if not site:
        raise HTTPException(404, f"Site {site_id} not found in cache")
    hardware = session.exec(select(Hardware).where(Hardware.site_id == site_id)).all()
    return {
        "site": _site_dict(site),
        "hardware": [_hw_dict(h) for h in hardware],
    }


@app.get("/api/sites/{site_id}/hardware/{hardware_id}")
def get_hardware_detail(site_id: int, hardware_id: int, session: Session = Depends(get_session)):
    hw = session.get(Hardware, hardware_id)
    if not hw or hw.site_id != site_id:
        raise HTTPException(404, f"Hardware {hardware_id} not found")
    result = _hw_dict(hw)
    if hw.gateway_id:
        gw = session.get(Gateway, hw.gateway_id)
        result["gateway"] = _gw_summary(gw) if gw else {"gatewayId": hw.gateway_id}
    return result


@app.get("/api/export/site/{site_id}")
def export_site(site_id: int, session: Session = Depends(get_session)):
    site = session.get(Site, site_id)
    if not site:
        raise HTTPException(404, f"Site {site_id} not found in cache")
    hardware = session.exec(select(Hardware).where(Hardware.site_id == site_id)).all()
    gateway_ids = {h.gateway_id for h in hardware if h.gateway_id}
    gateways = [session.get(Gateway, gid) for gid in gateway_ids]
    return {
        "site": json.loads(site.raw_json),
        "hardware": [json.loads(h.raw_json) for h in hardware],
        "gateways": [
            {
                "gatewayId": g.gateway_id,
                "name": g.name,
                "parameters": g.parameters(),
                "deviceConfigs": json.loads(g.device_configs_json),
            }
            for g in gateways if g
        ],
        "exportedAt": datetime.utcnow().isoformat(),
    }


@app.get("/api/export/csv/site/{site_id}")
def export_csv_site(
    site_id: int,
    job_name: str = "export",
    include_virtual: bool = True,
    session: Session = Depends(get_session),
):
    """Download a 31-column CSV for a single site."""
    site = session.get(Site, site_id)
    if not site:
        raise HTTPException(404, f"Site {site_id} not found in cache")
    csv_text = generate_csv(session, [site_id], job_name=job_name, include_virtual=include_virtual)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in job_name)
    filename = f"{safe_name}_{datetime.utcnow().strftime('%Y-%m-%d')}.csv"
    return Response(
        content=csv_text.encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class MultiSiteExportPayload(BaseModel):
    site_ids: list[int]
    job_name: str = "export"
    include_virtual: bool = True


@app.post("/api/export/csv")
def export_csv_multi(payload: MultiSiteExportPayload, session: Session = Depends(get_session)):
    """Download a 31-column CSV for multiple sites."""
    if not payload.site_ids:
        raise HTTPException(400, "site_ids must not be empty")
    csv_text = generate_csv(
        session,
        payload.site_ids,
        job_name=payload.job_name,
        include_virtual=payload.include_virtual,
    )
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in payload.job_name)
    filename = f"{safe_name}_{datetime.utcnow().strftime('%Y-%m-%d')}.csv"
    return Response(
        content=csv_text.encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Gateway endpoints
# ---------------------------------------------------------------------------

@app.get("/api/gateways")
def list_gateways(session: Session = Depends(get_session)):
    gateways = session.exec(select(Gateway)).all()
    result = []
    for gw in gateways:
        device_count = session.exec(
            select(func.count(Hardware.id)).where(Hardware.gateway_id == gw.gateway_id)
        ).one()
        result.append({
            "gatewayId": gw.gateway_id,
            "name": gw.name,
            "siteId": gw.site_id,
            "hardwareId": gw.hardware_id,
            "deviceCount": device_count,
            "lastSynced": gw.last_synced.isoformat() if gw.last_synced else None,
        })
    return result


@app.get("/api/gateways/{gateway_id}")
def get_gateway(gateway_id: str, session: Session = Depends(get_session)):
    gw = session.get(Gateway, gateway_id)
    if not gw:
        raise HTTPException(404, f"Gateway {gateway_id} not found")
    devices = session.exec(select(Hardware).where(Hardware.gateway_id == gateway_id)).all()
    return {
        "gatewayId": gw.gateway_id,
        "name": gw.name,
        "siteId": gw.site_id,
        "hardwareId": gw.hardware_id,
        "parameters": gw.parameters(),
        "deviceConfigs": json.loads(gw.device_configs_json),
        "devices": [_hw_dict(h) for h in devices],
        "lastSynced": gw.last_synced.isoformat() if gw.last_synced else None,
    }


# ---------------------------------------------------------------------------
# Migration jobs
# ---------------------------------------------------------------------------

# In-memory cancellation: job_id → (asyncio.Event, asyncio.Task)
_cancel_events: dict[int, asyncio.Event] = {}
_running_tasks: dict[int, asyncio.Task] = {}


class CreateJobPayload(BaseModel):
    name: str
    site_ids: list[int]
    include_virtual: bool = True
    include_data_devices: bool = True


def _job_dict(job: MigrationJob) -> dict:
    return {
        "id": job.id,
        "name": job.name,
        "status": job.status,
        "siteIds": job.site_ids(),
        "includeVirtual": job.include_virtual,
        "includeDataDevices": job.include_data_devices,
        "csvPath": job.csv_path,
        "sitesSynced": job.sites_synced,
        "devicesFound": job.devices_found,
        "virtualSkipped": job.virtual_skipped,
        "registersCaptured": job.registers_captured,
        "errorCount": job.error_count,
        "errorDetail": job.error_detail,
        "createdAt": job.created_at.isoformat() if job.created_at else None,
        "startedAt": job.started_at.isoformat() if job.started_at else None,
        "completedAt": job.completed_at.isoformat() if job.completed_at else None,
        "emailedAt": job.emailed_at.isoformat() if job.emailed_at else None,
    }


@app.post("/api/jobs")
def create_job(payload: CreateJobPayload, session: Session = Depends(get_session)):
    if not payload.name.strip():
        raise HTTPException(400, "Job name is required")
    if not payload.site_ids:
        raise HTTPException(400, "At least one site must be selected")
    job = MigrationJob(
        name=payload.name.strip(),
        status=JOB_STATUS_PENDING,
        site_ids_json=json.dumps(payload.site_ids),
        include_virtual=payload.include_virtual,
        include_data_devices=payload.include_data_devices,
        created_at=datetime.now(timezone.utc),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return _job_dict(job)


@app.get("/api/jobs")
def list_jobs(session: Session = Depends(get_session)):
    jobs = session.exec(select(MigrationJob).order_by(MigrationJob.created_at.desc())).all()
    return [_job_dict(j) for j in jobs]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(MigrationJob, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    return _job_dict(job)


@app.get("/api/jobs/{job_id}/events")
async def run_job(job_id: int, session: Session = Depends(get_session)):
    """SSE stream: sync selected sites then generate CSV."""
    job = session.get(MigrationJob, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    if job.status == JOB_STATUS_RUNNING:
        raise HTTPException(409, "Job is already running")

    cancel_event = asyncio.Event()
    _cancel_events[job_id] = cancel_event

    queue: asyncio.Queue = asyncio.Queue()
    site_ids = job.site_ids()

    async def _run():
        # Mark running
        job.status = JOB_STATUS_RUNNING
        job.started_at = datetime.now(timezone.utc)
        job.sites_synced = 0
        job.devices_found = 0
        job.virtual_skipped = 0
        job.registers_captured = 0
        job.error_count = 0
        job.error_detail = None
        session.add(job)
        session.commit()

        await queue.put({"type": "started", "total": len(site_ids)})

        total_devices = 0
        total_virtual = 0
        error_count = 0
        sites_done = 0

        for i, sid in enumerate(site_ids):
            if cancel_event.is_set():
                await queue.put({"type": "cancelled", "index": i, "total": len(site_ids)})
                break

            site = session.get(Site, sid)
            site_name = site.site_name if site else str(sid)
            await queue.put({"type": "site_start", "index": i + 1, "total": len(site_ids),
                             "siteId": sid, "siteName": site_name})
            try:
                count = await sync_site_hardware(session, sid)
                total_devices += count
                sites_done += 1
                await queue.put({"type": "site_done", "index": i + 1, "total": len(site_ids),
                                 "siteId": sid, "siteName": site_name, "deviceCount": count})
            except asyncio.CancelledError:
                # Propagate cancellation — task is being torn down
                raise
            except BaseException as exc:
                error_count += 1
                await queue.put({"type": "site_error", "index": i + 1, "total": len(site_ids),
                                 "siteId": sid, "siteName": site_name, "error": str(exc)})

        if cancel_event.is_set():
            job.status = JOB_STATUS_CANCELLED
            job.completed_at = datetime.now(timezone.utc)
            session.add(job)
            session.commit()
            await queue.put(None)
            return

        # Generate CSV
        await queue.put({"type": "generating_csv"})
        try:
            # Count virtual devices skipped
            from sqlmodel import select as sel
            for sid in site_ids:
                virt = session.exec(
                    sel(func.count(Hardware.id)).where(
                        Hardware.site_id == sid, Hardware.is_virtual_device == True
                    )
                ).one()
                total_virtual += virt

            csv_text = generate_csv(
                session, site_ids,
                job_name=job.name,
                include_virtual=job.include_virtual,
                include_data_devices=job.include_data_devices,
            )

            # Count registers from CSV (rows - 1 for header, minus BOM line)
            rows = csv_text.count("\r\n") - 1  # subtract header

            # Save CSV to exports dir
            data_dir = os.getcwd()  # set by run_backend.py to app data dir
            exports_dir = os.path.join(data_dir, "exports")
            os.makedirs(exports_dir, exist_ok=True)
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in job.name)
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            filename = f"{safe}_{date_str}.csv"
            csv_path = os.path.join(exports_dir, filename)
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                f.write(csv_text)

            job.status = JOB_STATUS_DONE
            job.csv_path = csv_path
            job.sites_synced = sites_done
            job.devices_found = total_devices
            job.virtual_skipped = total_virtual if not job.include_virtual else 0
            job.registers_captured = max(rows, 0)
            job.error_count = error_count
            job.completed_at = datetime.now(timezone.utc)
            session.add(job)
            session.commit()

            await queue.put({
                "type": "done",
                "sitesSynced": sites_done,
                "devicesFound": total_devices,
                "virtualSkipped": job.virtual_skipped,
                "registersCaptured": job.registers_captured,
                "errorCount": error_count,
                "csvPath": csv_path,
            })
        except Exception as exc:
            job.status = JOB_STATUS_ERROR
            job.error_detail = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            session.add(job)
            session.commit()
            await queue.put({"type": "error", "error": str(exc)})

        await queue.put(None)

    async def event_stream() -> AsyncIterator[str]:
        task = asyncio.create_task(_run())
        _running_tasks[job_id] = task
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            task.cancel()
            _cancel_events.pop(job_id, None)
            _running_tasks.pop(job_id, None)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(MigrationJob, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")

    # Signal cooperative cancellation (checked between sites)
    if job_id in _cancel_events:
        _cancel_events[job_id].set()

    # Hard-cancel the asyncio task so in-flight HTTP calls are interrupted immediately
    if job_id in _running_tasks:
        _running_tasks[job_id].cancel()

    # If no task reference (backend restarted with job stuck in running), force DB update
    if job_id not in _cancel_events and job_id not in _running_tasks:
        if job.status == JOB_STATUS_RUNNING:
            job.status = JOB_STATUS_CANCELLED
            job.completed_at = datetime.now(timezone.utc)
            job.error_detail = "Cancelled (backend was restarted while job was running)"
            session.add(job)
            session.commit()

    return {"ok": True}


@app.get("/api/jobs/{job_id}/csv")
def download_job_csv(job_id: int, session: Session = Depends(get_session)):
    job = session.get(MigrationJob, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    if not job.csv_path or not os.path.exists(job.csv_path):
        raise HTTPException(404, "CSV not available — run the job first")
    with open(job.csv_path, "r", encoding="utf-8-sig") as f:
        csv_text = f.read()
    filename = os.path.basename(job.csv_path)
    return Response(
        content=csv_text.encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/jobs/{job_id}/mark-emailed")
def mark_emailed(job_id: int, session: Session = Depends(get_session)):
    job = session.get(MigrationJob, job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    job.status = JOB_STATUS_EMAILED
    job.emailed_at = datetime.now(timezone.utc)
    session.add(job)
    session.commit()
    return _job_dict(job)


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@app.get("/api/admin/data-dir")
def data_dir():
    """Returns the directory where the DB and exports are stored."""
    return {"dataDir": os.getcwd(), "exportsDir": os.path.join(os.getcwd(), "exports")}


@app.post("/api/admin/clear-cache")
def clear_cache(session: Session = Depends(get_session)):
    """Wipe all cached sync data (sites, hardware, gateways). Migration jobs are preserved."""
    from sqlalchemy import text as sa_text
    with session.bind.connect() as conn:
        conn.execute(sa_text("DELETE FROM hardware"))
        conn.execute(sa_text("DELETE FROM gateways"))
        conn.execute(sa_text("DELETE FROM sites"))
        conn.commit()
    return {"ok": True}


@app.post("/api/admin/clear-migration-history")
def clear_migration_history(session: Session = Depends(get_session)):
    """Delete all migration jobs and their associated CSV paths."""
    from sqlalchemy import text as sa_text
    with session.bind.connect() as conn:
        conn.execute(sa_text("DELETE FROM migration_jobs"))
        conn.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Stats helper (used by dashboard)
# ---------------------------------------------------------------------------

@app.get("/api/stats")
def stats(session: Session = Depends(get_session)):
    site_count = session.exec(select(func.count(Site.site_id))).one()
    hw_count = session.exec(select(func.count(Hardware.id))).one()
    gw_count = session.exec(select(func.count(Gateway.gateway_id))).one()
    last_synced = session.exec(
        select(Site.last_synced).order_by(Site.last_synced.desc()).limit(1)
    ).first()
    return {
        "totalSites": site_count,
        "totalDevices": hw_count,
        "totalGateways": gw_count,
        "lastSynced": last_synced.isoformat() if last_synced else None,
    }


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _site_dict(s: Site) -> dict:
    return {
        "siteId": s.site_id,
        "siteName": s.site_name,
        "customerId": s.customer_id,
        "timezone": s.timezone,
        "lat": s.lat,
        "lng": s.lng,
        "address": s.address,
        "city": s.city,
        "state": s.state,
        "zipCode": s.zip_code,
        "country": s.country,
        "installDate": s.install_date,
        "turnOnDate": s.turn_on_date,
        "systemSizeKw": s.system_size_kw,
        "lastSynced": s.last_synced.isoformat() if s.last_synced else None,
    }


def _hw_dict(h: Hardware) -> dict:
    return {
        "id": h.id,
        "siteId": h.site_id,
        "name": h.name,
        "stringId": h.string_id,
        "functionCode": h.function_code,
        "serialNumber": h.serial_number,
        "flags": h.flags_list(),
        "timezone": h.timezone,
        "deviceType": h.device_type,
        # Modbus config (from list response)
        "modbusAddress": h.address,
        "portNumber": h.port_number,
        "baudRate": h.baud_rate,
        "comType": h.com_type,
        # Enriched detail fields
        "ipAddress": h.ip_address,
        "port": h.port,
        "portMode": h.port_mode,
        "gatewayId": h.gateway_id,
        "driverName": h.driver_name,
        "driverSettings": h.driver_settings(),
        "modbusUnitId": h.modbus_unit_id,
        "tcpPort": h.tcp_port,
        "isVirtualDevice": h.is_virtual_device,
        "lastSynced": h.last_synced.isoformat() if h.last_synced else None,
        "rawJson": json.loads(h.raw_json),
    }


def _gw_summary(gw: Gateway) -> dict:
    return {
        "gatewayId": gw.gateway_id,
        "name": gw.name,
        "siteId": gw.site_id,
        "hardwareId": gw.hardware_id,
        "parameters": gw.parameters(),
        "lastSynced": gw.last_synced.isoformat() if gw.last_synced else None,
    }


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

# In-memory scan state: True = scan running
_discovery_running: bool = False
_discovery_queue: asyncio.Queue | None = None


def _com_type_category(hw_dict: dict) -> str:
    """Classify a hardware API response dict as tcp/rtu/unknown.

    AlsoEnergy never sets comType="Tcp" for Modbus TCP devices — they arrive
    with comType="Unknown" but have driver.settings.TCPPort populated.
    """
    driver_settings = (hw_dict.get("driver") or {}).get("settings") or {}
    if driver_settings.get("TCPPort"):
        return "tcp"
    com_type = (hw_dict.get("config") or hw_dict.get("deviceConfig") or {}).get("comType")
    if com_type in ("Rs485_2Wire", "Rs485_4Wire", "Rs232", "Rs485"):
        return "rtu"
    return "unknown"


@app.get("/api/discovery/results")
def discovery_results(session: Session = Depends(get_session)):
    rows = session.exec(
        select(DiscoveryResult).order_by(
            DiscoveryResult.tcp_count.desc(),
            DiscoveryResult.site_name,
        )
    ).all()
    return [
        {
            "siteId": r.site_id,
            "siteName": r.site_name,
            "tcpCount": r.tcp_count,
            "rtuCount": r.rtu_count,
            "unknownCount": r.unknown_count,
            "lastScanned": r.last_scanned.isoformat() if r.last_scanned else None,
        }
        for r in rows
    ]


@app.get("/api/discovery/events")
async def discovery_scan_sse(session: Session = Depends(get_session)):
    """SSE stream: scan all sites for comType breakdown. Results cached in DB."""
    global _discovery_running, _discovery_queue

    if _discovery_running:
        raise HTTPException(409, "Scan already running")

    _discovery_running = True
    queue: asyncio.Queue = asyncio.Queue()
    _discovery_queue = queue

    async def _run():
        global _discovery_running
        try:
            sites_raw = await ae_client.get_sites()
            total = len(sites_raw)
            await queue.put({"type": "started", "total": total})

            sem = asyncio.Semaphore(5)

            async def _scan_site(i: int, raw: dict):
                site_id = raw["siteId"]
                site_name = raw.get("siteName") or raw.get("name") or str(site_id)
                async with sem:
                    await queue.put({
                        "type": "scanning",
                        "index": i + 1,
                        "total": total,
                        "siteId": site_id,
                        "siteName": site_name,
                    })
                    tcp = rtu = unknown = 0
                    try:
                        hw_resp = await ae_client.get_site_hardware(
                            site_id,
                            include_archived_fields=False,
                            include_summary_fields=False,
                            include_data_name_fields=False,
                            include_device_config=True,
                        )
                        items = (
                            hw_resp if isinstance(hw_resp, list)
                            else hw_resp.get("hardware") or hw_resp.get("items") or []
                        )
                        for hw in items:
                            cat = _com_type_category(hw)
                            if cat == "tcp":
                                tcp += 1
                            elif cat == "rtu":
                                rtu += 1
                            else:
                                unknown += 1
                    except Exception as exc:
                        await queue.put({
                            "type": "site_error",
                            "index": i + 1,
                            "total": total,
                            "siteId": site_id,
                            "siteName": site_name,
                            "error": str(exc),
                        })
                        return

                    # Upsert result
                    existing = session.get(DiscoveryResult, site_id)
                    if existing:
                        existing.site_name = site_name
                        existing.tcp_count = tcp
                        existing.rtu_count = rtu
                        existing.unknown_count = unknown
                        existing.last_scanned = datetime.now(timezone.utc)
                        session.add(existing)
                    else:
                        session.add(DiscoveryResult(
                            site_id=site_id,
                            site_name=site_name,
                            tcp_count=tcp,
                            rtu_count=rtu,
                            unknown_count=unknown,
                            last_scanned=datetime.now(timezone.utc),
                        ))
                    session.commit()

                    await queue.put({
                        "type": "site_done",
                        "index": i + 1,
                        "total": total,
                        "siteId": site_id,
                        "siteName": site_name,
                        "tcpCount": tcp,
                        "rtuCount": rtu,
                        "unknownCount": unknown,
                    })

            await asyncio.gather(
                *[_scan_site(i, raw) for i, raw in enumerate(sites_raw)],
                return_exceptions=True,
            )
            await queue.put({"type": "done", "total": total})
        except Exception as exc:
            await queue.put({"type": "error", "error": str(exc)})
        finally:
            _discovery_running = False
            await queue.put(None)

    async def event_stream() -> AsyncIterator[str]:
        task = asyncio.create_task(_run())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            task.cancel()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Entry point for PyInstaller binary
# ---------------------------------------------------------------------------

def run_server():
    import uvicorn

    parser = argparse.ArgumentParser(description="r3think migration tool backend")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    run_server()
