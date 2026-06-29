# N3uron Altus Power Meter Validator

Pulls `W`, `TOTWHEXP`, and `TOTWHIMP` from `MTR_001` for five Altus Power solar sites
via N3uron's REST API and saves an interactive Plotly HTML chart per site.

## Setup

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Fill in credentials from Bitwarden (search "N3uron" or "Altus")
python n3uron_validator.py
```

## Configuration (`.env`)

| Variable | Description |
|---|---|
| `N3URON_HOST` | `altuspower.r3thinklabs.io` |
| `N3URON_PORT` | `8443` |
| `N3URON_AUTH_TYPE` | `basic` or `token` |
| `N3URON_USERNAME` | Username (basic auth) |
| `N3URON_PASSWORD` | Password (basic auth) |
| `N3URON_TOKEN` | Bearer token (token auth) |
| `N3URON_VERIFY_SSL` | `false` — server uses a self-signed cert |
| `DAYS_BACK` | How many days of history to pull (default `7`) |

## Running

```bash
# Default: last 7 days (or DAYS_BACK from .env)
python n3uron_validator.py

# Custom date range
python n3uron_validator.py --start 2024-06-01 --end 2024-06-30
```

## Output

One HTML file per site, saved in the current directory:

| File | Site |
|---|---|
| `47098_SEARCHLIGHT_validation.html` | Searchlight |
| `49701_VALENCIA1_validation.html` | Valencia |
| `59722_DIX_SOLAR_validation.html` | Dix Solar |
| `37474_NEW_HOPE_ELLIS_FA_validation.html` | New Hope Ellis Farm |
| `57123_FLORENCE_validation.html` | Florence |

Open any file in a browser. Each chart has:
- **Left Y-axis** — W (Real Power, kW)
- **Right Y-axis #1** — TOTWHEXP (Export Energy, kWh)
- **Right Y-axis #2** — TOTWHIMP (Import Energy, kWh)
- Shared time X-axis with unified hover tooltip

## Tag paths used

```
/ALTUS/{SITE_FOLDER}/MTR/MTR_001/W
/ALTUS/{SITE_FOLDER}/MTR/MTR_001/TOTWHEXP
/ALTUS/{SITE_FOLDER}/MTR/MTR_001/TOTWHIMP
```

## Troubleshooting

| Error | Fix |
|---|---|
| `Authentication failed (401)` | Check username/password or token in `.env` |
| `Cannot reach altuspower.r3thinklabs.io:8443` | Confirm VPN/network access; check host and port |
| `SSL error` | Ensure `N3URON_VERIFY_SSL=false` in `.env` |
| Tag returns no data | Verify the date range has logged data in N3uron; check tag path in N3uron tag browser |
