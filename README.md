# AlsoEnergy → N3uron Migration Tool

Pulls site and device configuration from the AlsoEnergy PowerTrack API and presents it for review before designing the N3uron mapping layer.

## Setup

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env
# Edit .env — add ALSOENERGY_USERNAME and ALSOENERGY_PASSWORD
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
