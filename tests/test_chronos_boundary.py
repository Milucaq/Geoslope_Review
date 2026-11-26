"""CI tests transport/trust contracts with explicit doubles, not scientific forecasts."""

import hashlib
import json
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock
import sys
import subprocess

import numpy as np
import pytest

from gsreview.analytics import chronos_runtime
from gsreview.application.chronos import LocalChronos
from gsreview.domain.rules import ValidationError


PINS = {"chronos-forecasting": "2.3.2", "torch": "2.9.1+cpu", "transformers": "4.57.6",
        "accelerate": "1.16.0", "einops": "0.8.2", "numpy": "2.3.5", "pandas": "2.2.3"}


class TensorDouble:
    def __init__(self, values):
        self.values = np.asarray(values)

    def __getitem__(self, key):
        return TensorDouble(self.values[key])

    def cpu(self):
        return self

    def numpy(self):
        return self.values


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    config = tmp_path / "config"
    config.mkdir()
    spec = {"model_id": "amazon/chronos-2", "revision": "test-revision",
            "context_limit": 2048, "prediction_limit": 1024, "quantiles": [.1, .5, .9]}
    (config / "chronos2.json").write_text(json.dumps(spec))
    root = tmp_path / "models/chronos2/test-revision"
    root.mkdir(parents=True)
    hashes = {}
    for name in ("config.json", "model.safetensors"):
        (root / name).write_bytes(b"controlled asset")
        hashes[name] = hashlib.sha256(b"controlled asset").hexdigest()
    (config / "chronos2_assets.json").write_text(json.dumps(spec | {"files": hashes}))
    monkeypatch.setattr(chronos_runtime, "version", lambda package: PINS[package])
    pipeline = Mock()
    pipeline.predict_quantiles.side_effect = lambda x, **k: (
        [TensorDouble(np.ones((1, k["prediction_length"], 3)))], None,
    )
    loader = Mock(return_value=pipeline)
    monkeypatch.setitem(sys.modules, "chronos", SimpleNamespace(Chronos2Pipeline=SimpleNamespace(from_pretrained=loader)))
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        float32="float32", set_num_threads=Mock(), inference_mode=nullcontext,
    ))
    monkeypatch.setitem(sys.modules, "psutil", SimpleNamespace(
        Process=lambda: SimpleNamespace(memory_info=lambda: SimpleNamespace(rss=2**20, peak_wset=2**21)),
    ))
    return tmp_path, root, pipeline, loader


def test_runtime_verifies_offline_cpu_contract_and_batches_without_cross_learning(runtime):
    root, _, pipeline, loader = runtime
    jobs = [{"history": list(range(30)), "steps": 4}, {"history": list(range(2100)), "steps": 12}]
    output = chronos_runtime.run_jobs(root, jobs)
    assert [np.asarray(q).shape for q in output["predictions"]] == [(4, 3), (12, 3)]
    assert output["runtime"]["peak_working_set_mb"] == 2
    assert output["runtime"]["versions"] == PINS
    args = loader.call_args.kwargs
    assert args["local_files_only"] and args["use_safetensors"]
    assert args["trust_remote_code"] is False and args["device_map"] == "cpu"
    assert len(pipeline.predict_quantiles.call_args.args[0][0]) == 2048
    assert pipeline.predict_quantiles.call_args.kwargs["cross_learning"] is False


@pytest.mark.parametrize("case", ["hash", "version", "revision", "batch", "input"])
def test_runtime_rejects_invalid_assets_dependencies_or_requests(runtime, monkeypatch, case):
    root, assets, _, loader = runtime
    jobs = [{"history": list(range(30)), "steps": 4}]
    if case == "hash":
        (assets / "model.safetensors").write_bytes(b"tampered")
    elif case == "version":
        monkeypatch.setattr(chronos_runtime, "version", lambda _: "wrong")
    elif case == "revision":
        path = root / "config/chronos2_assets.json"
        manifest = json.loads(path.read_text())
        manifest["revision"] = "wrong"
        path.write_text(json.dumps(manifest))
    elif case == "batch":
        jobs = []
    else:
        jobs[0]["steps"] = 0
    with pytest.raises(ValueError):
        chronos_runtime.run_jobs(root, jobs)
    if case != "input":
        loader.assert_not_called()


def test_worker_boundary_is_optional_offline_and_rejects_failed_subprocess(tmp_path, monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    engine = LocalChronos(tmp_path)
    jobs = [{"history": [1., np.nan]*15, "steps": 4}]
    with pytest.raises(ValidationError, match="Falta"):
        engine.predict_many(jobs)
    executable = tmp_path / ".venv/chronos" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"test transport only")
    (tmp_path / "config").mkdir()
    (tmp_path / "config/chronos2_assets.json").write_text("{}")
    process = Mock(return_value=SimpleNamespace(stdout=json.dumps({"runtime": {"test": True}, "predictions": []})))
    monkeypatch.setattr(subprocess, "run", process)
    assert engine.predict_many(jobs) == []
    sent = json.loads(process.call_args.kwargs["input"])
    assert sent[0]["history"][1] is None
    assert process.call_args.kwargs["timeout"] == 300
    assert not process.call_args.kwargs.get("shell")
    process.side_effect = subprocess.TimeoutExpired("test", 300)
    with pytest.raises(ValidationError, match="sustitutos"):
        engine.predict_many(jobs)
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(ValidationError, match="Render"):
        engine.predict_many(jobs)
