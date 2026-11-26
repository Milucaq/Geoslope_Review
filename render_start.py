"""Render entry point: committed offline assets, external configuration, no ML download."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parent
    os.environ.setdefault("GEOSLOPE_SOURCE", str(root / "ci_artifacts"))
    os.environ.setdefault("GEOSLOPE_RUNTIME", str(Path(tempfile.gettempdir()) / "geoslope_review"))
    os.environ.setdefault("RENDER", "true")
    port = int(os.environ.get("PORT", "10000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be a valid TCP port")
    command = [sys.executable, "-m", "streamlit", "run", str(root / "app.py"),
               "--server.address=0.0.0.0", f"--server.port={port}", "--server.headless=true",
               "--server.enableXsrfProtection=true", "--server.enableCORS=true"]
    return subprocess.call(command, cwd=root)


if __name__ == "__main__":
    raise SystemExit(main())
