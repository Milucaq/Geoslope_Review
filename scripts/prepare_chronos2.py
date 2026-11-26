"""Explicit public checkpoint download, separate from app/CI and frozen artifacts."""

import argparse
import hashlib
import json
import re
from pathlib import Path
import urllib.request
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]


def require_https(url):
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Checkpoint downloads and redirects require HTTPS without embedded credentials")


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        require_https(newurl)
        return super().redirect_request(request, response, code, message, headers, newurl)


def open_https(url, timeout):
    require_https(url)
    return urllib.request.build_opener(HTTPSRedirect()).open(url, timeout=timeout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true", required=True)
    parser.parse_args()
    spec = json.loads((ROOT / "config/chronos2.json").read_text())
    revision = spec["revision"]
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Expected an immutable checkpoint commit SHA")
    base = "https://huggingface.co/amazon/chronos-2"
    with open_https(
        f"https://huggingface.co/api/models/amazon/chronos-2/revision/{revision}?blobs=true", timeout=60,
    ) as response:
        metadata = json.load(response)
    if metadata["sha"] != revision:
        raise RuntimeError("Checkpoint revision mismatch")
    expected = {entry["rfilename"]: entry for entry in metadata["siblings"]}
    root = ROOT / "models/chronos2" / revision
    root.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name in ("config.json", "model.safetensors"):
        path = root / name
        digest = hashlib.sha256()
        temporary = root / (name + ".partial")
        with open_https(f"{base}/resolve/{revision}/{name}", timeout=120) as response:
            with temporary.open("wb") as output:
                chunks = 0
                while chunk := response.read(4 * 1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)
                    chunks += 1
                    if chunks % 16 == 0:
                        print(f"{name}: {chunks*4} MiB downloaded", flush=True)
        hashes[name] = digest.hexdigest()
        if name.endswith(".safetensors") and hashes[name] != expected[name]["lfs"]["sha256"]:
            raise RuntimeError("Model hash mismatch")
        temporary.replace(path)
        print(f"Verified {name}: {hashes[name]}", flush=True)
    manifest = {"model_id": spec["model_id"], "revision": revision, "files": hashes}
    (ROOT / "config/chronos2_assets.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
