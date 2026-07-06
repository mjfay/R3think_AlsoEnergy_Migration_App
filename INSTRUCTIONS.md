# Asset Owner Export Tool — Instructions

## What this tool does
Connects to your API, pulls your site and device configuration, and exports it as a CSV file for N3uron migration. Everything runs locally on your machine — no data is sent anywhere.

---

## Requirements
- **Mac or Windows** computer
- **Python 3.10 or later** installed
  - Mac: download from [python.org](https://python.org) or install via Homebrew (`brew install python`)
  - Windows: download from [python.org](https://python.org) — check "Add Python to PATH" during install
- Your **API username and password**

---

## First-time setup (one time only, takes ~1 minute)

### Mac
1. Unzip the folder if you haven't already
2. Double-click **run.command**
3. If you see a security warning, go to **System Settings → Privacy & Security** and click **Open Anyway**
4. A terminal window will open and install dependencies automatically
5. Your browser will open to the app

### Windows
1. Unzip the folder
2. Double-click **run.bat**
3. If Windows Defender shows a warning, click **More info → Run anyway**
4. A command prompt will install dependencies automatically
5. Your browser will open to the app

---

## Every time after that
Just double-click **run.command** (Mac) or **run.bat** (Windows). The app opens in your browser within a few seconds.

---

## First use — entering your credentials
1. The app will show an onboarding screen — click **Get started**
2. Enter your API username and password
3. Click **Test connection** — the connection is verified automatically
4. Click **Save & continue** — credentials are held in server memory for your browser session only, never written to disk, and cleared when you log out or restart the app

---

## Exporting data

### Sync your sites
1. On the **Dashboard**, click **Select Sites…**
2. Choose which sites to pull hardware data from and click **Sync Selected Sites**

### Run an export
1. Go to **Export Wizard** in the top nav
2. Select the sites you want and configure export options
3. Create the job — it syncs all selected sites and generates a CSV
4. When complete, download the CSV from the **Dashboard**'s exports list or directly from the job page

---

## Stopping the app
Close the terminal/command prompt window that opened when you launched the app. Your browser tab will stop working — that's expected.

---

## Troubleshooting

**"Not authenticated" error**
Go to **Settings → Re-enter credentials** and enter your API credentials again.

**Browser doesn't open automatically**
Open your browser manually and go to: `http://127.0.0.1:8000`

**Port already in use**
Another instance of the app is already running. Close the other terminal window first, then relaunch.

**Python not found (Windows)**
Reinstall Python from [python.org](https://python.org) and make sure to check "Add Python to PATH" during installation.
