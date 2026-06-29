# Next Steps — Bucket B: GitHub Push + CI Build

## Pre-flight status (completed 2026-06-26)

| Check | Result |
|---|---|
| A1: Dev app + site picker + SSE | ✅ Passed |
| A2: Production DMG installed & boots | ✅ Passed |
| A3: build.yml reviewed + Windows alias fix | ✅ Patched |
| A4: Git repo state | ⚠️ No repo yet — see step 1 |
| A5: DMG copied to deliverables/ | ✅ `deliverables/v0.1.0/asset-owner-export-tool_0.1.0_aarch64.dmg` |

---

## Step 1 — Create GitHub repo

1. Go to github.com → New repository
   - Name: `asset-owner-export-tool` (or whatever you want)
   - Private ✅
   - No README, no .gitignore (we have our own)

2. Copy the SSH or HTTPS remote URL shown after creation.

---

## Step 2 — Initialize local git and push

```bash
cd /Users/michaelfay/Documents/R3think_AlsoEnergy_Migration_App

git init
git add .
git commit -m "feat: initial release v0.1.0

- Tauri + FastAPI + React desktop app
- AlsoEnergy site picker (1,298 sites, live search)
- TCP device detection via driver.settings.TCPPort
- GitHub Actions CI for macOS/Windows/Linux"

git remote add origin <YOUR_GITHUB_URL>
git push -u origin main
```

---

## Step 3 — Tag v0.1.0 to trigger CI builds

```bash
git tag v0.1.0
git push origin v0.1.0
```

The push of a `v*` tag triggers `.github/workflows/build.yml` automatically.
Three parallel jobs run: macOS DMG, Windows MSI, Linux AppImage.

---

## Step 4 — Download artifacts from GitHub Actions

1. Go to your repo on GitHub → **Actions** tab
2. Click the "Build Installers" workflow run for the `v0.1.0` tag
3. Wait for all 3 jobs to go green (~15–25 min)
4. Download artifacts at the bottom of the run page:
   - `asset-owner-export-tool-macos` → contains `.dmg`
   - `asset-owner-export-tool-windows` → contains `.msi`
   - `asset-owner-export-tool-linux` → contains `.AppImage`

---

## Step 5 — Upload to SharePoint

Upload the three installer files to the agreed SharePoint folder so your boss can access them.

The macOS DMG from the local build is already in:
```
deliverables/v0.1.0/asset-owner-export-tool_0.1.0_aarch64.dmg
```
(This folder is in .gitignore — not pushed to GitHub.)

---

## Step 6 — Notify your boss (Slack template)

```
Hey — the Asset Owner Export Tool v0.1.0 is ready.

Uploaded to SharePoint: [link]

Files:
• macOS: asset-owner-export-tool_0.1.0_aarch64.dmg  (Apple Silicon)
• Windows: asset-owner-export-tool_0.1.0_x64_en-US.msi
• Linux: asset-owner-export-tool_0.1.0_amd64.AppImage

Install notes:
- macOS: open the DMG, drag to Applications. On first launch, macOS will ask for keychain access — click Allow.
- Windows: run the MSI, follow the wizard.
- On first launch, click Settings (⚙) and enter your AlsoEnergy credentials.
  They're stored in the OS keychain — never written to disk.

Let me know if you hit any issues.
```

---

## Known notes for the recipient

- **macOS first-launch keychain prompt**: expected — click "Allow". Only happens once per install.
- **Re-authentication on each launch**: by design (OAuth tokens live in memory only).
- **TCP devices**: the app now correctly detects Modbus TCP devices via `driver.settings.TCPPort`. Run a full sync to populate IP addresses for ~97 previously-missed TCP devices.
- **"Export" vs "Migration"**: UI says "Export" everywhere. Internal DB tables/API routes still say "migration" for compatibility — this is intentional.
