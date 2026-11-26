"""Offline worker boundary: optional heavy libraries never enter the web process."""

import json
import os
from pathlib import Path
import subprocess
import time

import numpy as np

from gsreview.domain.rules import ValidationError


class LocalChronos:
    def __init__(self, root):
        self.root = Path(root)
        self.runtime = {}

    def availability(self):
        if os.environ.get("RENDER"):
            return False, "Chronos-2 local no está habilitado en Render; requiere inferencia independiente dimensionada."
        relative = "Scripts/python.exe" if os.name == "nt" else "bin/python"
        ready = (self.root / ".venv/chronos" / relative).is_file() and (self.root / "config/chronos2_assets.json").is_file()
        return ready, ("Chronos-2 CPU local preparado; la ejecución verificará dependencias y hashes."
                       if ready else "Chronos-2 no disponible: falta el worker opcional o el checkpoint verificado. No se simulan pronósticos.")

    def predict_many(self, jobs):
        if os.environ.get("RENDER"):
            raise ValidationError("Chronos local deshabilitado en Render hasta validar memoria y arquitectura.")
        relative = "Scripts/python.exe" if os.name == "nt" else "bin/python"
        executable = self.root / ".venv/chronos" / relative
        if not executable.is_file() or not (self.root / "config/chronos2_assets.json").is_file():
            raise ValidationError("Falta el entorno CPU opcional o el checkpoint verificado de Chronos-2.")
        safe_jobs = [{"history": [float(x) if np.isfinite(x) else None for x in job["history"]],
                      "steps": job["steps"]} for job in jobs]
        try:
            started = time.perf_counter()
            process = subprocess.run(
                [str(executable), str(self.root / "scripts/chronos_worker.py")],
                input=json.dumps(safe_jobs, allow_nan=False), capture_output=True, text=True,
                timeout=300, cwd=self.root, check=True,
            )
            output = json.loads(process.stdout)
            self.runtime = output["runtime"]
            self.runtime["worker_wall_seconds"] = time.perf_counter()-started
            return output["predictions"]
        except (subprocess.SubprocessError, OSError, ValueError, KeyError) as exc:
            raise ValidationError("El worker Chronos no pudo completar el pronóstico local; no hay resultados sustitutos.") from exc
