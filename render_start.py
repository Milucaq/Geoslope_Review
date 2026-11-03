import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent

os.environ["GEOSLOPE_SOURCE"] = str(root / "ci_artifacts")
os.environ["GEOSLOPE_RUNTIME"] = "/tmp/geoslope_review"

port = os.environ.get("PORT", "10000")

command = [
    sys.executable,
    "-m",
    "streamlit",
    "run",
    str(root / "app.py"),
    "--server.address=0.0.0.0",
    f"--server.port={port}",
    "--server.headless=true",
    "--server.enableXsrfProtection=true",
    "--server.enableCORS=true",
]

raise SystemExit(subprocess.call(command, cwd=root))
