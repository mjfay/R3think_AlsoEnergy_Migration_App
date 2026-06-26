import sys
import os
import traceback

_LOG = os.path.expanduser("~/Library/Application Support/r3think-migration-tool/backend.log")

try:
    os.makedirs(os.path.dirname(_LOG), exist_ok=True)
    _logfile = open(_LOG, "w", buffering=1)

    if getattr(sys, 'frozen', False):
        data_dir = os.path.dirname(_LOG)
        if sys.platform.startswith("win"):
            data_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "r3think-migration-tool")
        elif sys.platform.startswith("linux"):
            data_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "r3think-migration-tool")
        os.makedirs(data_dir, exist_ok=True)
        os.chdir(data_dir)
        sys.stdout = _logfile
        sys.stderr = _logfile

    _logfile.write(f"run_backend starting, frozen={getattr(sys, 'frozen', False)}, cwd={os.getcwd()}\n")
    _logfile.flush()

    from app.main import run_server
    _logfile.write("imports OK, calling run_server\n")
    _logfile.flush()
    run_server()

except Exception:
    try:
        with open(_LOG, "a") as f:
            f.write("\n--- FATAL ---\n")
            traceback.print_exc(file=f)
    except Exception:
        pass
    sys.exit(1)
