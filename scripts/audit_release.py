"""Audit exact indexed release files without reading forbidden private file contents."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = {
    "private-key": re.compile(rb"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY(?: BLOCK)?-----"),
    "github-token": re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})\b"),
    "huggingface-token": re.compile(rb"\bhf_[A-Za-z0-9]{30,}\b"),
    "aws-access-key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
}


def forbidden(path):
    p = PurePosixPath(path)
    parts = [part.lower() for part in p.parts]
    name = p.name.lower()
    if not p.parts or p.is_absolute() or ".." in p.parts or ":" in path:
        return "unsafe-path"
    if parts[0] == "data" or any(part in {"node_modules", ".venv", "venv", ".aws", ".codex", ".git", "tmp"} for part in parts):
        return "private-or-generated-directory"
    if any(part.startswith(("runtime", "respaldo")) or part in {"backups", "checkpoints"} for part in parts[:-1]):
        return "runtime-backup-checkpoint"
    if name.startswith(".env") and path != ".env.example" or name in {"secrets.toml", ".npmrc", ".pypirc", ".netrc", "_netrc", "id_rsa", "id_ed25519"}:
        return "credentials"
    if p.suffix.lower() in {".tif", ".tiff", ".safetensors", ".pt", ".pth", ".ckpt", ".partial", ".key", ".pem",
                             ".p12", ".pfx", ".db", ".sqlite", ".sqlite3", ".gsbackup", ".pyc", ".zip", ".7z", ".rar", ".tar", ".gz"}:
        return "private-or-large-source-format"
    if name.endswith(("-wal", "-shm")) or "__pycache__" in parts:
        return "database-sidecar-or-cache"
    if "chronos2" in parts and parts[0] == "models":
        return "optional-checkpoint"
    trusted_models = {"ci_artifacts/models/phase5/"+name for name in
                      ("isolation_forest.joblib", "preprocessing_pipeline.joblib", "scoring_bundle.joblib")}
    if p.suffix in {".joblib", ".pkl", ".pickle"} and path not in trusted_models:
        return "unapproved-serialized-model"
    return None


def inspect_blob(path, content):
    findings = []
    if len(content) >= 100*1024**2:
        findings.append("github-file-size-limit")
    if PurePosixPath(path).suffix.lower() in {".py", ".js", ".json", ".md", ".yaml", ".yml", ".toml", ".txt", ".html", ".csv"} or path == ".env.example":
        findings.extend(name for name, pattern in SECRET_PATTERNS.items() if pattern.search(content))
    return findings


def audit(root=ROOT, staged=False):
    command = ["git", "-C", str(root)]
    args = ["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"] if staged else ["ls-files", "-z"]
    paths = subprocess.check_output(command+args).decode("utf-8").split("\0")
    rows, violations = [], []
    for path in sorted(p for p in paths if p):
        reason = forbidden(path)
        if reason:
            violations.append({"path": path, "rule": reason})
            continue  # Never open a prohibited file or print its contents.
        content = subprocess.check_output(command+["show", ":"+path])
        findings = inspect_blob(path, content)
        violations.extend({"path": path, "rule": finding} for finding in findings)
        rows.append({"path": path, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    return {"scope": "staged-changes" if staged else "index-tree", "files": rows,
            "total_bytes": sum(row["bytes"] for row in rows), "violations": violations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = audit(staged=args.staged)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"files": len(report["files"]), "total_bytes": report["total_bytes"], "violations": report["violations"]}))
    return bool(report["violations"])


if __name__ == "__main__":
    raise SystemExit(main())
