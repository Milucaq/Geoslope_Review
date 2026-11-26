"""Publication boundaries and clean-start contracts use controlled files and runtimes."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

import render_start
from scripts import audit_release, prepare_chronos2, verify_release_assets


@pytest.mark.parametrize("path", [".env", ".env.production", "data/runtime_nuevo/users.json", "data/respaldo/key",
    "assets/terrain/source.TIFF", "models/chronos2/revision/model.safetensors", ".venv/bin/python",
    "checkpoints/epoch.ckpt", "data.db-wal", "case.gsbackup", "../private.py", "tmp/export.json",
    "node_modules/pkg/index.js", "ci_artifacts/models/phase5/unapproved.joblib", ".npmrc", "id_ed25519"])
def test_publication_policy_rejects_private_and_generated_files(path):
    assert audit_release.forbidden(path)


def test_publication_policy_keeps_approved_public_assets_and_masks_secret_values():
    for path in (".env.example", "assets/terrain/john_henry/mesh.npz", "config/chronos2_assets.json",
                 "ci_artifacts/models/phase5/isolation_forest.joblib", "reports/science/synthetic_backtest.csv"):
        assert audit_release.forbidden(path) is None
    token = ("hf_"+"a"*40).encode()
    assert audit_release.inspect_blob("example.py", token) == ["huggingface-token"]


def test_audit_uses_index_snapshot_and_never_reads_a_prohibited_blob(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "safe.py").write_text("print('safe')\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SYNTHETIC_PRIVATE_SENTINEL=do-not-open", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "--force", "--", "safe.py", ".env"], check=True)
    (tmp_path / "safe.py").write_text("unindexed edit", encoding="utf-8")
    original = subprocess.check_output
    def checked(command, *args, **kwargs):
        assert ":.env" not in command
        return original(command, *args, **kwargs)
    monkeypatch.setattr(audit_release.subprocess, "check_output", checked)
    result = audit_release.audit(tmp_path)
    assert result["violations"] == [{"path": ".env", "rule": "credentials"}]
    assert result["files"][0]["sha256"] == hashlib.sha256(b"print('safe')\n").hexdigest()


@pytest.mark.parametrize("url", ["http://huggingface.co/model", "file:///private.key", "ftp://host/weights",
                                "https://user:password@host/weights", "https:///missing-host"])
def test_optional_download_rejects_unsafe_schemes_and_redirects(url, monkeypatch):
    opener = Mock()
    monkeypatch.setattr(prepare_chronos2.urllib.request, "build_opener", opener)
    with pytest.raises(ValueError):
        prepare_chronos2.open_https(url, 10)
    with pytest.raises(ValueError):
        prepare_chronos2.HTTPSRedirect().redirect_request(None, None, 302, "redirect", {}, url)
    opener.assert_not_called()


def test_optional_download_uses_validated_https_without_network(monkeypatch):
    opener = Mock()
    factory = Mock(return_value=opener)
    monkeypatch.setattr(prepare_chronos2.urllib.request, "build_opener", factory)
    assert prepare_chronos2.open_https("https://huggingface.co/amazon/chronos-2", 60) == opener.open.return_value
    opener.open.assert_called_once_with("https://huggingface.co/amazon/chronos-2", timeout=60)


def test_bundle_manifest_detects_source_edits_and_nonlocal_resources(tmp_path):
    root = tmp_path / "assets/three_component"
    (root / "src").mkdir(parents=True)
    (root / "public").mkdir()
    (root / "bundle/assets").mkdir(parents=True)
    for name in ("package.json", "package-lock.json"):
        (root / name).write_text("{}", encoding="utf-8")
    (root / "index.html").write_text("<html></html>", encoding="utf-8")
    (root / "src/main.js").write_text("const x = 1;\n", encoding="utf-8")
    (root / "bundle/index.html").write_text('<script src="./assets/main.js"></script>', encoding="utf-8")
    (root / "bundle/LICENSE_THREE.txt").write_text("Controlled test license", encoding="utf-8")
    (root / "bundle/assets/main.js").write_text("const x=1;", encoding="utf-8")
    before = verify_release_assets.bundle_manifest(tmp_path)
    (root / "src/main.js").write_bytes(b"const x = 1;\r\n")
    assert verify_release_assets.bundle_manifest(tmp_path) == before
    (root / "src/main.js").write_text("const x = 2;", encoding="utf-8")
    assert verify_release_assets.bundle_manifest(tmp_path) != before
    (root / "bundle/index.html").write_text('<script src="https://remote.example/script.js"></script>', encoding="utf-8")
    with pytest.raises(ValueError, match="offline asset"):
        verify_release_assets.bundle_manifest(tmp_path)


def test_render_entry_keeps_configured_runtime_and_security_flags(monkeypatch, tmp_path):
    monkeypatch.setenv("GEOSLOPE_RUNTIME", str(tmp_path))
    monkeypatch.delenv("GEOSLOPE_SOURCE", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("PORT", "10001")
    launch = Mock(return_value=0)
    monkeypatch.setattr(render_start.subprocess, "call", launch)
    assert render_start.main() == 0
    arguments = launch.call_args.args[0]
    assert "--server.port=10001" in arguments
    assert "--server.enableXsrfProtection=true" in arguments
    assert "--server.enableCORS=true" in arguments
    assert os.environ["GEOSLOPE_RUNTIME"] == str(tmp_path)
    assert os.environ["RENDER"] == "true"
    monkeypatch.setenv("PORT", "65536")
    with pytest.raises(ValueError, match="TCP port"):
        render_start.main()


def test_clean_start_from_an_unrelated_directory_without_private_inputs(tmp_path):
    root = Path(__file__).resolve().parents[1]
    environment = os.environ | {"GEOSLOPE_KEY_FILE": str(tmp_path / "must-not-be-created.key")}
    result = subprocess.run([sys.executable, str(root / "scripts/verify_clean_start.py")], cwd=tmp_path,
                            capture_output=True, text=True, check=True, env=environment)
    report = json.loads(result.stdout)
    assert report["artifacts"] == 17 and report["source"] == "ci_artifacts"
    assert report["application_from_checkout"] is True
    assert report["chronos_loaded"] is False and report["runtime"] == "temporary"
    assert not (tmp_path / "must-not-be-created.key").exists()
