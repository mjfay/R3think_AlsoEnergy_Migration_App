import multiprocessing
multiprocessing.freeze_support()  # MUST be first for PyInstaller on Windows

import os
import sys
import traceback


def _data_dir() -> str:
    """Return the platform-appropriate writable data directory."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "r3think-migration-tool")
    elif sys.platform.startswith("darwin"):
        return os.path.join(
            os.path.expanduser("~"),
            "Library", "Application Support", "r3think-migration-tool",
        )
    else:
        xdg = os.environ.get(
            "XDG_DATA_HOME",
            os.path.join(os.path.expanduser("~"), ".local", "share"),
        )
        return os.path.join(xdg, "r3think-migration-tool")


def _emergency_path() -> str:
    """Always-writable crash log path so Windows users can find the error."""
    if sys.platform.startswith("win"):
        temp = os.environ.get("TEMP", os.environ.get("TMP", "C:\\temp"))
        try:
            os.makedirs(temp, exist_ok=True)
        except Exception:
            temp = "C:\\temp"
            try:
                os.makedirs(temp, exist_ok=True)
            except Exception:
                pass
        return os.path.join(temp, "r3think-backend-error.txt")
    else:
        import tempfile
        return os.path.join(tempfile.gettempdir(), "r3think-backend-error.txt")


_LOG = None

try:
    app_data_dir = _data_dir()
    os.makedirs(app_data_dir, exist_ok=True)

    _LOG = os.path.join(app_data_dir, "backend.log")
    _logfile = open(_LOG, "w", buffering=1, encoding="utf-8")

    _logfile.write(
        f"run_backend starting\n"
        f"  frozen={getattr(sys, 'frozen', False)}\n"
        f"  platform={sys.platform}\n"
        f"  data_dir={app_data_dir}\n"
    )
    _logfile.flush()

    if getattr(sys, "frozen", False):
        # Point httpx at the bundled certifi cert store so HTTPS calls work.
        try:
            import certifi
            cert_path = certifi.where()
            os.environ["SSL_CERT_FILE"] = cert_path
            os.environ["REQUESTS_CA_BUNDLE"] = cert_path
            _logfile.write(f"  certifi: {cert_path}\n")
        except Exception as e:
            _logfile.write(f"  certifi unavailable ({e}) — HTTPS may fail\n")
        _logfile.flush()

        # chdir so SQLite resolves sqlite:///./alsoenergy.db into the data dir.
        os.chdir(app_data_dir)
        sys.stdout = _logfile
        sys.stderr = _logfile

    _logfile.write(f"  cwd={os.getcwd()}\n")
    _logfile.flush()

    from app.main import run_server  # noqa: E402

    _logfile.write("imports OK, calling run_server\n")
    _logfile.flush()
    run_server()

except Exception:
    tb = traceback.format_exc()

    # Write to the normal log if it was opened
    if _LOG:
        try:
            with open(_LOG, "a", encoding="utf-8") as f:
                f.write("\n--- FATAL ERROR ---\n")
                f.write(tb)
        except Exception:
            pass

    # Also write to an emergency path the user can always find
    emergency = _emergency_path()
    try:
        with open(emergency, "w", encoding="utf-8") as f:
            f.write("r3think backend fatal startup error\n")
            f.write(f"Normal log: {_LOG}\n")
            f.write(f"Platform: {sys.platform}\n\n")
            f.write(tb)
    except Exception:
        pass

    sys.exit(1)
