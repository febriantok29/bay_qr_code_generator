from __future__ import annotations

import shutil
from pathlib import Path

ARTIFACT_RELPATHS = [
    "build",
    ".dart_tool",
    "ios/Pods",
    "ios/Podfile.lock",
    "macos/Pods",
    "macos/Podfile.lock",
]


def find_flutter_projects(root: Path) -> list[Path]:
    return sorted({p.parent for p in root.rglob("pubspec.yaml") if p.is_file()})


def list_subdirs(path: Path) -> list[Path]:
    entries = [
        p for p in path.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    ]
    return sorted(entries, key=lambda p: p.name.lower())


def dir_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def scan_project(project_dir: Path) -> dict:
    artifacts = []
    for relpath in ARTIFACT_RELPATHS:
        abspath = project_dir / relpath
        if not abspath.exists():
            continue
        artifacts.append({
            "relpath": relpath,
            "abspath": abspath,
            "size": dir_size(abspath),
            "is_dir": abspath.is_dir(),
        })
    return {
        "path": project_dir,
        "name": project_dir.name,
        "artifacts": artifacts,
        "total_size": sum(a["size"] for a in artifacts),
    }


def scan_root(root: Path) -> list[dict]:
    projects = [scan_project(p) for p in find_flutter_projects(root)]
    return [p for p in projects if p["artifacts"]]


def clean_project(project_dir: Path, relpaths: list[str]) -> dict:
    removed = []
    freed_bytes = 0
    for relpath in relpaths:
        abspath = project_dir / relpath
        if not abspath.exists():
            continue
        freed_bytes += dir_size(abspath)
        if abspath.is_dir():
            shutil.rmtree(abspath)
        else:
            abspath.unlink()
        removed.append(relpath)
    return {"removed": removed, "freed_bytes": freed_bytes}
