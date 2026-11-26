"""Check the committed offline bundle and optimized terrain without source rasters."""

import argparse
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def digest(path, text=False):
    raw = path.read_bytes()
    if text:
        raw = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def bundle_manifest(root):
    component = root / "assets/three_component"
    source = [component / name for name in ("package.json", "package-lock.json", "index.html")]
    source += [p for name in ("src", "public") for p in (component / name).rglob("*") if p.is_file()]
    bundle = component / "bundle"
    files = [p for p in bundle.rglob("*") if p.is_file() and p.name != "build_manifest.json"]
    if not (bundle / "index.html").is_file() or not (bundle / "LICENSE_THREE.txt").is_file():
        raise ValueError("Missing offline Three.js bundle or license")
    html = (bundle / "index.html").read_text(encoding="utf-8")
    references = re.findall(r'(?:src|href)=["\x27]([^"\x27]+)', html)
    for reference in references:
        target = (bundle / reference).resolve()
        if ":" in reference or reference.startswith("/") or not target.is_relative_to(bundle.resolve()) or not target.is_file():
            raise ValueError("Bundle resource must be an existing relative offline asset")
    return {"schema": 1, "sources": {p.relative_to(component).as_posix(): digest(p, True) for p in sorted(source)},
            "files": {p.relative_to(bundle).as_posix(): digest(p, True) for p in sorted(files)}}


def verify(root=ROOT):
    component = root / "assets/three_component"
    expected = json.loads((component / "bundle/build_manifest.json").read_text(encoding="utf-8"))
    if bundle_manifest(root) != expected:
        raise ValueError("Three.js bundle is stale or altered; rebuild and regenerate its manifest")
    terrain = root / "assets/terrain/john_henry"
    metadata = json.loads((terrain / "metadata.json").read_text(encoding="utf-8"))
    for name in ("mesh.npz", "texture.jpg"):
        if digest(terrain / name) != metadata["asset_hashes"][name]:
            raise ValueError("Optimized John Henry asset is altered: "+name)
    century = root / "assets/terrain"
    metadata = json.loads((century / "metadata.json").read_text(encoding="utf-8"))
    if digest(century / "century_surface.npz") != metadata["asset_sha256"]:
        raise ValueError("Optimized Century asset is altered")
    return {"bundle_files": len(expected["files"]), "source_files": len(expected["sources"]), "terrain_assets": 3}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-bundle-manifest", action="store_true", help="Run only after an explicit npm build")
    args = parser.parse_args()
    if args.write_bundle_manifest:
        path = ROOT / "assets/three_component/bundle/build_manifest.json"
        path.write_text(json.dumps(bundle_manifest(ROOT), indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(verify(), sort_keys=True))


if __name__ == "__main__":
    main()
