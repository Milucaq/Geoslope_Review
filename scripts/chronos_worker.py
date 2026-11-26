"""JSON stdin/stdout protocol; no credentials, network or application database."""

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

from gsreview.analytics.chronos_runtime import run_jobs


if __name__ == "__main__":
    jobs = json.loads(sys.stdin.read(2*1024*1024))
    print(json.dumps(run_jobs(ROOT, jobs), allow_nan=False))
