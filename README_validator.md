# N3uron Site Data Validator

Pulls historical `W`, `TOTWHEXP`, and `TOTWHIMP` meter tags from N3uron's REST API
for five solar sites and saves an interactive Plotly HTML chart per site.

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure credentials
cp .env.example .env
# Open .env and fill in your N3uron host, port, and credentials
```

## Configuration (`.env`)

| Variable | Description |
|---|---|
| `N3URON_HOST` | IP address or hostname of the N3uron server |
| `N3URON_PORT` | REST API port — default `3443` (HTTPS) or `3003` (HTTP) |
| `N3URON_AUTH_TYPE` | `basic` or `token` |
| `N3URON_USERNAME` | Username (basic auth only) |
| `N3URON_PASSWORD` | Password (basic auth only) |
| `N3URON_TOKEN` | Bearer token (token auth only) |
| `N3URON_VERIFY_SSL` | `false` to skip SSL cert verification (self-signed certs) |

## Running

```bash
# Default: last 7 days
python n3uron_validator.py

# Custom date range (ISO 8601)
python n3uron_validator.py --start 2024-01-01 --end 2024-01-31
```

## Output

One HTML file per site saved in the current directory:

- `Searchlight_validation.html`
- `Valencia_validation.html`
- `Dix_Solar_validation.html`
- `New_Hope_Ellis_Farm_validation.html`
- `Florence_validation.html`

Open any file in a browser for an interactive chart with zoom, pan, and hover.

## Tag path discovery

The script calls `GET /tag?cmd=browse` to find tag paths automatically.
Discovered paths are printed to the console so you can verify them.

If auto-discovery fails (tag tree structure doesn't match expected patterns),
open `n3uron_validator.py` and uncomment the `MANUAL_PATHS` block near the
bottom of the file, filling in the exact paths from your N3uron tag browser.

To explore the tag tree interactively from Python:

```python
from n3uron_validator import browse_tags
print(browse_tags("/"))          # top-level folders
print(browse_tags("/Searchlight"))  # children of a specific node
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `SSL certificate verification failed` | Set `N3URON_VERIFY_SSL=false` in `.env` |
| `Cannot connect to N3uron` | Check `N3URON_HOST` and `N3URON_PORT`; confirm firewall allows access |
| `No tags found for site` | Use `browse_tags("/")` to inspect the tree; set paths manually |
| `No data returned` for a tag | Verify the tag has logged data in the requested time range |
