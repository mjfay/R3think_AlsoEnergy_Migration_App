#!/usr/bin/env bash
# -----------------------------------------------------------------------
# AlsoEnergy Asset Owner Export Tool — Mac/Linux launcher
# Run this script to start the export.
# On first run it creates a .venv folder and installs dependencies.
# No admin (sudo) rights required.
# -----------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Find Python 3.10+ -----------------------------------------------
find_python() {
    for cmd in python3.12 python3.11 python3.10 python3 python; do
        if command -v "$cmd" &>/dev/null; then
            if "$cmd" -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON=$(find_python || true)
if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.10 or later was not found."
    echo "Please install it from https://www.python.org/downloads/ or via your package manager."
    exit 1
fi

# --- Set up virtual environment on first run -------------------------
if [ ! -f ".venv/bin/activate" ]; then
    echo "Setting up environment for the first time. This takes about 30 seconds..."
    "$PYTHON" -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
    echo "Setup complete."
    echo
else
    # shellcheck disable=SC1091
    source .venv/bin/activate
fi

# --- Run the export --------------------------------------------------
python export.py "$@"
