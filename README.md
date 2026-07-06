# Asset Owner Export Tool

Pulls site and device configuration from your API and exports it to CSV.

## Quick start (no installation required)

**Mac / Linux:** double-click `run.sh`, or open a terminal and run `./run.sh`.  
**Windows:** double-click `run.bat`.

The first time you run it, the script silently installs its own dependencies into a private folder — this takes about a minute and only happens once. After that, it starts the app and opens it automatically in your default browser. You don't need to install anything, open a terminal, or know anything about Python. To stop the app, close the terminal window that appeared when you launched it (Mac/Linux) or press any key in the console window (Windows).

---

## Developer setup

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env
# No credentials go in .env — each user enters their own API login in the
# browser, held in-memory for their session only.
```

### Frontend

```bash
cd frontend
npm install
```

## Running

**Terminal 1 — backend:**
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
# Runs on http://localhost:8000
```

**Terminal 2 — frontend:**
```bash
cd frontend
npm run dev
# Runs on http://localhost:5173
```

## First sync

1. Open http://localhost:5173
2. Check the connection badge top-right — should show "Token valid"
3. Click **Sync All** on the dashboard — a drawer slides out showing live progress per site
4. Once done, go to **Sites** to browse cached data
5. Click any site → Devices tab to see hardware config
6. Click a device for full config detail with copy buttons

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Token status |
| GET | `/api/stats` | Counts + last sync time |
| POST | `/api/sync/sites` | Pull all sites (no hardware) |
| POST | `/api/sync/site/{id}` | Pull one site + its hardware |
| GET | `/api/sync/all` | SSE stream: pull all sites + hardware |
| GET | `/api/sites` | List cached sites |
| GET | `/api/sites/{id}` | Site detail + hardware list |
| GET | `/api/sites/{id}/hardware/{hwId}` | Single device detail |
| GET | `/api/export/site/{id}` | JSON export (future mapper input) |
