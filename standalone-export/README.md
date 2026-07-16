# AlsoEnergy Asset Owner Export Tool

Exports your AlsoEnergy site and device data to a CSV file — no installation required.

---

## What you need

- **Windows, Mac, or Linux**
- **Python 3.10 or later** already installed on the computer
  - Check by opening a terminal/command prompt and running: `python --version` or `python3 --version`
  - If you don't have it: [python.org/downloads](https://www.python.org/downloads/) — on Windows, check **"Add Python to PATH"** during setup

---

## Quick start

### Step 1 — Set up your credentials

Copy the `.env.example` file to a new file called `.env` (in the same folder), then open it in any text editor and fill in your AlsoEnergy username and password:

```
ALSOENERGY_USERNAME=your-username
ALSOENERGY_PASSWORD=your-password
```

> If you skip this step, the tool will ask for your credentials interactively each time it runs.

### Step 2 — Run the export

**Windows:** Double-click `run.bat`

**Mac / Linux:** Open a terminal in this folder and run:
```bash
./run.sh
```

The first time you run it, the tool will spend about 30 seconds setting up a local Python environment. Subsequent runs start immediately.

### Step 3 — Find your CSV

The CSV file is saved in the `exports/` folder inside this directory, named with the date and time:

```
exports/export_2025-06-24_143022.csv
```

Open it in Excel, Google Sheets, or any spreadsheet application.

---

## Options

You can pass flags to the launcher to customize the export.

**Windows (Command Prompt):**
```
run.bat --job-name "Q2-Migration"
run.bat --sites 12345 67890
run.bat --no-virtual
```

**Mac / Linux:**
```bash
./run.sh --job-name "Q2-Migration"
./run.sh --sites 12345 67890
./run.sh --no-virtual
```

| Flag | Description |
|------|-------------|
| `--job-name NAME` | Label embedded in every CSV row (default: `export`) |
| `--output-dir DIR` | Folder for the CSV file (default: `exports/`) |
| `--sites ID [ID ...]` | Export only specific site IDs instead of all sites |
| `--no-virtual` | Exclude virtual devices |
| `--no-data-devices` | Exclude data/gateway devices (function codes DA/CE/RD/GW) |

---

## CSV format

The output is a 31-column UTF-8 CSV (with BOM for Excel compatibility). Columns:

`migration_job_name`, `site_id`, `site_name`, `site_timezone`, `gateway_id`, `gateway_name`, `channel_mode`, `channel_host`, `channel_tcp_port`, `channel_serial_port`, `channel_baud_rate`, `device_id`, `device_name`, `device_string_id`, `device_function_code`, `device_type`, `device_serial_number`, `modbus_unit_id`, `is_enabled`, `is_virtual_device`, `driver_name`, `register_group`, `tag_name`, `tag_modbus_address`, `tag_raw_value`, `tag_value`, `tag_is_archived`, `tag_data_type`, `archived_field_name`, `generated_at`, `tool_version`

---

## Security notes

- Your credentials are **never** written to disk by the tool itself. They stay in your `.env` file, which only you control.
- The `.env` file is read-only by the local Python process; it is not transmitted anywhere except to the AlsoEnergy API for authentication.
- The `.venv/` folder contains only the Python libraries needed to run the tool (no credentials or data).

---

## Troubleshooting

**"Python was not found"** — Install Python 3.10+ from [python.org](https://www.python.org/downloads/). On Windows, make sure to check "Add Python to PATH" during installation.

**"Authentication failed"** — Double-check your username and password in `.env`. Verify you can log in at [alsoenergy.com](https://alsoenergy.com).

**"Permission denied" on Mac/Linux** — Run `chmod +x run.sh` in the terminal, then try again.

**The export is slow** — This is normal for large accounts. The tool fetches detailed metadata for every device in parallel. A site with 50+ devices may take 10–30 seconds.

**Need to reset the environment** — Delete the `.venv/` folder and run the launcher again. It will rebuild from scratch.
