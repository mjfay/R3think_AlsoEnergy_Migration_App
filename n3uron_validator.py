"""
N3uron historical tag validator — Altus Power solar sites.
Pulls W, TOTWHEXP, TOTWHIMP from MTR_001 for each site and saves
an interactive Plotly HTML chart per site.
"""

import os
import sys
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

HOST = os.getenv("N3URON_HOST", "altuspower.r3thinklabs.io")
PORT = os.getenv("N3URON_PORT", "8443")
AUTH_TYPE = os.getenv("N3URON_AUTH_TYPE", "basic").lower()
USERNAME = os.getenv("N3URON_USERNAME", "")
PASSWORD = os.getenv("N3URON_PASSWORD", "")
TOKEN = os.getenv("N3URON_TOKEN", "")
VERIFY_SSL = os.getenv("N3URON_VERIFY_SSL", "false").lower() not in ("false", "0", "no")
DAYS_BACK = int(os.getenv("DAYS_BACK", "7"))

BASE_URL = f"https://{HOST}:{PORT}/tag"

# Confirmed site folder names from live tag tree
SITES = {
    "Searchlight":        "47098_SEARCHLIGHT",
    "Valencia":           "49701_VALENCIA1",
    "Dix Solar":          "59722_DIX_SOLAR",
    "New Hope Ellis Farm":"37474_NEW_HOPE_ELLIS_FA",
    "Florence":           "57123_FLORENCE",
}

TAGS = ["W", "TOTWHEXP", "TOTWHIMP"]

TAG_LABELS = {
    "W":         "Real Power, 3p Total (kW)",
    "TOTWHEXP":  "Export Energy, 3p Total (kWh)",
    "TOTWHIMP":  "Import Energy, 3p Total (kWh)",
}

TAG_COLORS = {
    "W":        "#1f77b4",   # blue
    "TOTWHEXP": "#ff7f0e",   # orange
    "TOTWHIMP": "#2ca02c",   # green
}

DEFAULT_END = datetime.now(timezone.utc)
DEFAULT_START = DEFAULT_END - timedelta(days=DAYS_BACK)


# ---------------------------------------------------------------------------
# HTTP session
# ---------------------------------------------------------------------------

def _build_session() -> requests.Session:
    s = requests.Session()
    if AUTH_TYPE == "token":
        s.headers["Authorization"] = f"Bearer {TOKEN}"
    elif AUTH_TYPE == "basic":
        s.auth = (USERNAME, PASSWORD)
    s.verify = VERIFY_SSL
    if not VERIFY_SSL:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    return s


SESSION = _build_session()


def _get(params: dict) -> Optional[object]:
    try:
        resp = SESSION.get(BASE_URL, params=params, timeout=60)
        if resp.status_code == 401:
            log.error(
                "Authentication failed (401). Check N3URON_USERNAME/PASSWORD or TOKEN in .env."
            )
            return None
        if resp.status_code == 403:
            log.error("Access denied (403). The account may lack permission for this tag path.")
            return None
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.SSLError:
        log.error(
            "SSL error connecting to %s. If using a self-signed cert, "
            "set N3URON_VERIFY_SSL=false in .env.",
            BASE_URL,
        )
        return None
    except requests.exceptions.ConnectionError:
        log.error(
            "Cannot reach %s. Check that the host/port is correct and you are on the right network.",
            BASE_URL,
        )
        return None
    except requests.exceptions.HTTPError as exc:
        log.error("HTTP %s: %s", exc.response.status_code, exc.response.text[:200])
        return None
    except Exception as exc:
        log.error("Unexpected error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Tag path builder
# ---------------------------------------------------------------------------

def tag_path(site_folder: str, tag: str) -> str:
    return f"/ALTUS/{site_folder}/MTR/MTR_001/{tag}"


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_history_many(
    paths: list[str],
    start: datetime,
    end: datetime,
) -> dict[str, list[dict]]:
    """Fetch raw history for multiple tags in a single request."""
    data = _get(
        {
            "cmd": "historyMany",
            "paths": ",".join(paths),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "options.mode": "raw",
        }
    )
    if data is None:
        return {}
    # N3uron returns {"/path": [{t, v}, ...], ...}
    if isinstance(data, dict):
        return data
    # Some versions return [{path: ..., data: [...]}, ...]
    if isinstance(data, list):
        result = {}
        for item in data:
            p = item.get("path") or item.get("tag") or item.get("name")
            records = item.get("data") or item.get("values") or []
            if p:
                result[p] = records
        return result
    return {}


def fetch_history_single(
    path: str,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Fetch raw history for a single tag path."""
    data = _get(
        {
            "cmd": "history",
            "path": path,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "options.mode": "raw",
        }
    )
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("data") or data.get("values") or data.get("records") or []
    return []


def _to_dataframe(records: list[dict]) -> pd.DataFrame:
    """Convert a list of {t, v} records to a sorted DataFrame."""
    rows = []
    for rec in records:
        t = rec.get("t") or rec.get("timestamp") or rec.get("time")
        v = rec.get("v") or rec.get("value")
        if t is None or v is None:
            continue
        if isinstance(t, (int, float)):
            t = datetime.fromtimestamp(t / 1000 if t > 1e10 else t, tz=timezone.utc)
        else:
            t = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
        rows.append({"timestamp": t, "value": float(v)})
    if not rows:
        return pd.DataFrame(columns=["timestamp", "value"])
    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Charting
# ---------------------------------------------------------------------------

def build_chart(
    site_name: str,
    tag_frames: dict[str, pd.DataFrame],
    start: datetime,
    end: datetime,
) -> go.Figure:
    """
    Build a Plotly figure with three Y-axes:
      - W on the left (y1)
      - TOTWHEXP on the right (y2)
      - TOTWHIMP on the far right (y3)
    """
    fig = go.Figure()

    yaxis_map = {
        "W":        "y",
        "TOTWHEXP": "y2",
        "TOTWHIMP": "y3",
    }

    for tag, df in tag_frames.items():
        if df.empty:
            log.warning("  %s: no data — trace skipped.", tag)
            continue
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=df["value"],
                name=f"{tag} — {TAG_LABELS[tag]}",
                line=dict(color=TAG_COLORS[tag], width=1.5),
                yaxis=yaxis_map[tag],
            )
        )

    date_fmt = "%Y-%m-%d"
    fig.update_layout(
        title=dict(
            text=(
                f"{site_name} — Meter Validation "
                f"({start.strftime(date_fmt)} to {end.strftime(date_fmt)})"
            ),
            font=dict(size=16),
        ),
        xaxis=dict(
            title="Time",
            domain=[0.08, 0.84],  # leave room for two right-side axes
        ),
        yaxis=dict(
            title="W — Real Power (kW)",
            titlefont=dict(color=TAG_COLORS["W"]),
            tickfont=dict(color=TAG_COLORS["W"]),
        ),
        yaxis2=dict(
            title="TOTWHEXP — Export Energy (kWh)",
            titlefont=dict(color=TAG_COLORS["TOTWHEXP"]),
            tickfont=dict(color=TAG_COLORS["TOTWHEXP"]),
            overlaying="y",
            side="right",
            anchor="x",
        ),
        yaxis3=dict(
            title="TOTWHIMP — Import Energy (kWh)",
            titlefont=dict(color=TAG_COLORS["TOTWHIMP"]),
            tickfont=dict(color=TAG_COLORS["TOTWHIMP"]),
            overlaying="y",
            side="right",
            anchor="free",
            position=0.92,
        ),
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.8)"),
        hovermode="x unified",
        height=600,
        margin=dict(r=160),
    )
    return fig


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(start: datetime, end: datetime) -> None:
    log.info("Date range : %s → %s", start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    log.info("Server     : %s:%s", HOST, PORT)
    log.info("Auth type  : %s", AUTH_TYPE)
    log.info("SSL verify : %s", VERIFY_SSL)
    log.info("")

    for site_name, site_folder in SITES.items():
        log.info("── %s (%s) ──", site_name, site_folder)

        paths = [tag_path(site_folder, tag) for tag in TAGS]

        # Try bulk fetch first
        bulk = fetch_history_many(paths, start, end)

        tag_frames: dict[str, pd.DataFrame] = {}
        for tag in TAGS:
            path = tag_path(site_folder, tag)
            if bulk and path in bulk:
                records = bulk[path]
            else:
                log.info("  historyMany miss for %s — falling back to single fetch", tag)
                records = fetch_history_single(path, start, end)

            df = _to_dataframe(records)
            if df.empty:
                log.warning("  %s (%s): no data in range.", tag, path)
            else:
                log.info("  %s: %d points  (%.2f – %.2f)", tag, len(df), df["value"].min(), df["value"].max())
            tag_frames[tag] = df

        fig = build_chart(site_name, tag_frames, start, end)
        filename = f"{site_folder}_validation.html"
        fig.write_html(filename)
        log.info("  Saved → %s", filename)
        log.info("")

    log.info("Done.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="N3uron Altus Power meter validator")
    parser.add_argument(
        "--start",
        help="Start datetime ISO 8601, e.g. 2024-01-01 (defaults to DAYS_BACK days ago)",
        default=None,
    )
    parser.add_argument(
        "--end",
        help="End datetime ISO 8601 (defaults to now)",
        default=None,
    )
    args = parser.parse_args()

    start_dt = (
        datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
        if args.start
        else DEFAULT_START
    )
    end_dt = (
        datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
        if args.end
        else DEFAULT_END
    )

    run(start_dt, end_dt)
