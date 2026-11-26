"""Optional offline CPU runtime; imported only inside the dedicated worker."""

import hashlib
import json
from importlib.metadata import version
from pathlib import Path
import time

import numpy as np


def run_jobs(root, jobs):
    root = Path(root)
    spec = json.loads((root / "config/chronos2.json").read_text())
    manifest = json.loads((root / "config/chronos2_assets.json").read_text())
    if manifest["revision"] != spec["revision"] or manifest["model_id"] != spec["model_id"]:
        raise ValueError("Checkpoint no fijado")
    if not 1 <= len(jobs) <= 4:
        raise ValueError("Batch no válido")
    versions = {}
    for package in ("chronos-forecasting", "torch", "transformers", "accelerate", "einops", "numpy", "pandas"):
        versions[package] = version(package)
    pins = {"chronos-forecasting": "2.3.2", "torch": "2.9.1+cpu", "transformers": "4.57.6",
            "accelerate": "1.16.0", "einops": "0.8.2", "numpy": "2.3.5", "pandas": "2.2.3"}
    if versions != pins:
        raise ValueError("Dependencias Chronos incompatibles")
    model_root = root / "models/chronos2" / spec["revision"]
    for name in ("config.json", "model.safetensors"):
        digest = hashlib.sha256()
        with (model_root / name).open("rb") as stream:
            while chunk := stream.read(4*1024*1024):
                digest.update(chunk)
        if digest.hexdigest() != manifest["files"][name]:
            raise ValueError("Checkpoint alterado")
    import torch
    import psutil
    from chronos import Chronos2Pipeline

    started = time.perf_counter()
    torch.set_num_threads(2)
    pipeline = Chronos2Pipeline.from_pretrained(
        str(model_root), device_map="cpu", torch_dtype=torch.float32,
        local_files_only=True, trust_remote_code=False, use_safetensors=True,
    )
    load_seconds = time.perf_counter()-started
    predictions = []
    with torch.inference_mode():
        for job in jobs:
            values = np.asarray(job["history"], dtype=np.float32)
            steps = job["steps"]
            if (values.ndim != 1 or np.isinf(values).any() or np.isfinite(values).sum() < 20
                    or type(steps) is not int or not 1 <= steps <= spec["prediction_limit"]):
                raise ValueError("Serie u horizonte Chronos no válido")
            q, _ = pipeline.predict_quantiles(
                [values[-spec["context_limit"]:]], prediction_length=steps,
                quantile_levels=spec["quantiles"], batch_size=1, cross_learning=False,
            )
            predictions.append(q[0][0].cpu().numpy().astype(float).tolist())
    memory = psutil.Process().memory_info()
    return {"predictions": predictions, "runtime": {
        "model_id": spec["model_id"], "revision": spec["revision"], "versions": versions,
        "device": "cpu", "load_seconds": load_seconds, "elapsed_seconds": time.perf_counter()-started,
        "rss_mb": memory.rss/1024**2,
        "peak_working_set_mb": getattr(memory, "peak_wset", 0)/1024**2 or None,
        "context_limit": spec["context_limit"],
    }}
