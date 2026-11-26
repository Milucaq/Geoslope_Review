"""Smoke check against committed assets and a fresh temporary runtime, without secrets."""

import json
import os
from pathlib import Path
import platform
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gsreview.application.container import Container
from gsreview.application.chronos import LocalChronos
from scripts.verify_release_assets import verify


def check():
    keys = ("GEOSLOPE_SOURCE", "GEOSLOPE_RUNTIME", "GEOSLOPE_KEY_FILE", "RENDER")
    previous = {key: os.environ.get(key) for key in keys}
    try:
        with tempfile.TemporaryDirectory(prefix="geoslope-release-") as directory:
            os.environ.update(GEOSLOPE_SOURCE=str(ROOT / "ci_artifacts"), GEOSLOPE_RUNTIME=directory,
                              GEOSLOPE_KEY_FILE=str(Path(directory) / "master.key"), RENDER="true")
            container = Container()
            try:
                if not Path(sys.modules[Container.__module__].__file__).resolve().is_relative_to(ROOT):
                    raise RuntimeError("Application imports must come from this checkout")
                count = container.reader.verify()
                if count != 17 or container.science._model is not None:
                    raise RuntimeError("Startup must verify 17 artifacts without loading an inference model")
                if LocalChronos(ROOT).availability()[0] or any(name in sys.modules for name in ("torch", "transformers", "chronos")):
                    raise RuntimeError("Heavy optional models must not load in Render")
                return {"platform": platform.system(), "application_from_checkout": True, "artifacts": count, "source": "ci_artifacts",
                        "runtime": "temporary", "chronos_loaded": False, "assets": verify(ROOT)}
            finally:
                container.store.engine.dispose()
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True))
