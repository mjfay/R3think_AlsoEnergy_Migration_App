"""
N3uron historical tag validator for solar site monitoring.
Pulls W, TOTWHEXP, TOTWHIMP for each site and saves interactive HTML charts.
"""

import os
import sys
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

HOST = os.getenv("N3URON_HOST", "localhost")
PORT = os.getenv("N3URON_PORT", "3443")
AUTH_TYPE = os.getenv("N3URON_AUTH_TYPE", "basic").lower()
USERNAME = os.getenv("N3URON_USERNAME", "")
PASSWORD = os.getenv("N3URON_PASSWORD", "")
TOKEN = os.getenv("N3URON_TOKEN", "")
VERIFY_SSL = os.getenv("N3URON_VERIFY_SSL", "false").lower() not in ("false", "0", "no")

BASE_URL = f"https://{HOST}:{PORT}/tag"

SITES = [
    "Searchlight",
    "Valencia",
    "Dix Solar",
    "New Hope Ellis Farm",
    "Florence",
]

TAGS_OF_INTEREST = ["W", "TOTWHEXP", "TOTWHIMP"]

# Default: last 7 days
DEFAULT_END = datetime.now(timezone.utc)
DEFAULT_START = DEFAULT_END - timedelta(days=7)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _session() -> requests.Session:
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


SESSION = _session()


def _get(params: dict) -> Optional[dict]:
    try:
        resp = SESSION.get(BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.SSLError:
        log.error(
            "SSL certificate verification failed. Set N3URON_VERIFY_SSL=false in .env "
            "if using a self-signed certificate."
        )
        return None
    except requests.exceptions.ConnectionError as exc:
        log.error("Cannot connect to N3uron at %s: %s", BASE_URL, exc)
        return None
    except requests.exceptions.HTTPError as exc:
        log.error("HTTP error %s for params %s", exc.response.status_code, params)
        return None
    except Exception as exc:
        log.error("Unexpected error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Tag discovery
# ---------------------------------------------------------------------------

def browse_tags(path_prefix: str = "") -> list[str]:
    """Return child tag/folder names under path_prefix."""
    data = _get({"cmd": "browse", "path": path_prefix})
    if data is None:
        return []
    # N3uron browse typically returns a list or a dict with a 'tags'/'children' key
    if isinstance(data, list):
        return [item.get("name", "") for item in data]
    if isinstance(data, dict):
        items = data.get("tags") or data.get("children") or data.get("items") or []
        return [item.get("name", "") for item in items]
    return []


def discover_site_tags(site_name: str) -> dict[str, str]:
    """
    Browse the tag tree looking for W, TOTWHEXP, TOTWHIMP under the given site.
    Returns {tag_name: full_tag_path} for found tags.
    Prints discovered paths so the user can verify them before data is pulled.
    """
    log.info("Discovering tags for site: %s", site_name)
    found: dict[str, str] = {}

    # Try common root path patterns
    candidate_roots = [
        f"/{site_name}",
        f"/{site_name.replace(' ', '_')}",
        f"/Sites/{site_name}",
        f"/Solar/{site_name}",
        site_name,
    ]

    for root in candidate_roots:
        children = browse_tags(root)
        if not children:
            continue
        log.info("  Found tag tree at: %s  (children: %s)", root, children[:10])
        for tag in TAGS_OF_INTEREST:
            # Check direct children first
            if tag in children:
                path = f"{root}/{tag}"
                found[tag] = path
                log.info("  Discovered %s -> %s", tag, path)
            else:
                # One level deeper — look inside each child folder
                for child in children:
                    grandchildren = browse_tags(f"{root}/{child}")
                    if tag in grandchildren:
                        path = f"{root}/{child}/{tag}"
                        found[tag] = path
                        log.info("  Discovered %s -> %s", tag, path)
        if found:
            break

    if not found:
        log.warning(
            "  No tags found for '%s'. Check that the site name matches the N3uron tag tree. "
            "Run browse_tags('/') to see top-level paths.",
            site_name,
        )
    return found


# ---------------------------------------------------------------------------
# Historical data
# ---------------------------------------------------------------------------

def fetch_history(
    tag_path: str,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Fetch raw historical data for a single tag path."""
    data = _get(
        {
            "cmd": "history",
            "path": tag_path,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "options.mode": "raw",
        }
    )
    if data is None:
        return []
    # Response may be a list of {t, v} records or wrapped in a key
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("data") or data.get("values") or data.get("records") or []
    return []


def fetch_history_many(
    tag_paths: list[str],
    start: datetime,
    end: datetime,
) -> dict[str, list[dict]]:
    """Fetch raw historical data for multiple tags in one request."""
    data = _get(
        {
            "cmd": "historyMany",
            "paths": ",".join(tag_paths),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "options.mode": "raw",
        }
    )
    if data is None:
        return {}
    # Expected: {<path>: [{t, v}, ...], ...}  or  [{path: ..., data: [...]}, ...]
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        result = {}
        for item in data:
            path = item.get("path") or item.get("tag")
            records = item.get("data") or item.get("values") or []
            if path:
                result[path] = records
        return result
    return {}


def _parse_records(records: list[dict]) -> tuple[list, list]:
    """Return (timestamps, values) lists from a list of {t, v} dicts."""
    timestamps, values = [], []
    for rec in records:
        t = rec.get("t") or rec.get("timestamp") or rec.get("time")
        v = rec.get("v") or rec.get("value")
        if t is None or v is None:
            continue
        # t may be epoch ms, epoch s, or ISO string
        if isinstance(t, (int, float)):
            if t > 1e10:  # milliseconds
                t = datetime.fromtimestamp(t / 1000, tz=timezone.utc)
            else:
                t = datetime.fromtimestamp(t, tz=timezone.utc)
        else:
            t = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
        timestamps.append(t)
        values.append(v)
    return timestamps, values


# ---------------------------------------------------------------------------
# Charting
# ---------------------------------------------------------------------------

TAG_COLORS = {
    "W": "#1f77b4",
    "TOTWHEXP": "#ff7f0e",
    "TOTWHIMP": "#2ca02c",
}

TAG_UNITS = {
    "W": "W",
    "TOTWHEXP": "Wh",
    "TOTWHIMP": "Wh",
}


def build_chart(
    site_name: str,
    tag_data: dict[str, tuple[list, list]],
    start: datetime,
    end: datetime,
) -> go.Figure:
    """
    tag_data: {tag_name: (timestamps, values)}
    W on left Y-axis; TOTWHEXP on right; TOTWHIMP on far-right.
    """
    fig = make_subplots(specs=[[{"secondary_y": False}]])

    # We need three y-axes: primary (W), secondary (TOTWHEXP), tertiary (TOTWHIMP)
    y_axis_map = {
        "W": "y1",
        "TOTWHEXP": "y2",
        "TOTWHIMP": "y3",
    }

    for tag_name, (ts, vs) in tag_data.items():
        if not ts:
            log.info("  Skipping %s — no data points.", tag_name)
            continue
        fig.add_trace(
            go.Scatter(
                x=ts,
                y=vs,
                name=f"{tag_name} ({TAG_UNITS.get(tag_name, '')})",
                line=dict(color=TAG_COLORS.get(tag_name, "#888")),
                yaxis=y_axis_map.get(tag_name, "y1"),
            )
        )

    date_fmt = "%Y-%m-%d"
    fig.update_layout(
        title=f"{site_name} — {start.strftime(date_fmt)} to {end.strftime(date_fmt)}",
        xaxis=dict(title="Time", domain=[0.12, 0.88]),
        yaxis=dict(
            title=f"W ({TAG_UNITS['W']})",
            titlefont=dict(color=TAG_COLORS["W"]),
            tickfont=dict(color=TAG_COLORS["W"]),
        ),
        yaxis2=dict(
            title=f"TOTWHEXP ({TAG_UNITS['TOTWHEXP']})",
            titlefont=dict(color=TAG_COLORS["TOTWHEXP"]),
            tickfont=dict(color=TAG_COLORS["TOTWHEXP"]),
            overlaying="y",
            side="right",
        ),
        yaxis3=dict(
            title=f"TOTWHIMP ({TAG_UNITS['TOTWHIMP']})",
            titlefont=dict(color=TAG_COLORS["TOTWHIMP"]),
            tickfont=dict(color=TAG_COLORS["TOTWHIMP"]),
            overlaying="y",
            side="right",
            anchor="free",
            position=1.0,
        ),
        legend=dict(x=0.01, y=0.99),
        hovermode="x unified",
        height=600,
    )
    return fig


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    override_tag_paths: Optional[dict[str, dict[str, str]]] = None,
):
    """
    override_tag_paths: {site_name: {tag_name: tag_path}}
    Pass this if tag discovery doesn't find paths automatically.
    """
    start = start or DEFAULT_START
    end = end or DEFAULT_END

    log.info("Date range: %s → %s", start.isoformat(), end.isoformat())
    log.info("SSL verification: %s", VERIFY_SSL)

    for site in SITES:
        log.info("=" * 60)
        log.info("Site: %s", site)

        # Resolve tag paths
        if override_tag_paths and site in override_tag_paths:
            tag_paths = override_tag_paths[site]
        else:
            tag_paths = discover_site_tags(site)

        if not tag_paths:
            log.warning("Skipping %s — no tag paths found.", site)
            continue

        # Fetch data (prefer historyMany for efficiency, fall back per-tag)
        paths_list = list(tag_paths.values())
        bulk = fetch_history_many(paths_list, start, end)

        tag_data: dict[str, tuple[list, list]] = {}
        for tag_name, path in tag_paths.items():
            if bulk and path in bulk:
                records = bulk[path]
            else:
                log.info("  Falling back to single-tag fetch for %s", tag_name)
                records = fetch_history(path, start, end)

            if not records:
                log.warning("  %s (%s): no data returned.", tag_name, path)
                tag_data[tag_name] = ([], [])
            else:
                ts, vs = _parse_records(records)
                log.info("  %s: %d points", tag_name, len(ts))
                tag_data[tag_name] = (ts, vs)

        fig = build_chart(site, tag_data, start, end)
        filename = f"{site.replace(' ', '_')}_validation.html"
        fig.write_html(filename)
        log.info("Saved: %s", filename)

    log.info("Done.")


if __name__ == "__main__":
    # Optionally accept --start and --end as CLI args (ISO 8601)
    import argparse

    parser = argparse.ArgumentParser(description="N3uron site data validator")
    parser.add_argument("--start", help="Start datetime (ISO 8601)", default=None)
    parser.add_argument("--end", help="End datetime (ISO 8601)", default=None)
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

    # --- Override tag paths here if auto-discovery doesn't find them ---
    # Example:
    # MANUAL_PATHS = {
    #     "Searchlight": {
    #         "W": "/Searchlight/Meter/W",
    #         "TOTWHEXP": "/Searchlight/Meter/TOTWHEXP",
    #         "TOTWHIMP": "/Searchlight/Meter/TOTWHIMP",
    #     },
    # }
    # run(start_dt, end_dt, override_tag_paths=MANUAL_PATHS)

    run(start_dt, end_dt)
