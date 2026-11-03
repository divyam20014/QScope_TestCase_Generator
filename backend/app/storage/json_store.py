"""Atomic JSON persistence with rolling backups.

Every write: serialize -> write to a temp file in the same directory ->
fsync -> os.replace (atomic on both POSIX and Windows) -> rotate backups.
A read that encounters corrupt JSON automatically falls back to the most
recent backup instead of raising, so a crash mid-write never loses data
beyond the last successful save.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

MAX_BACKUPS = 5


def _backup_dir(path: Path) -> Path:
    backup_dir = path.parent / ".backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return _recover_from_backup(path, default)


def _recover_from_backup(path: Path, default: Any) -> Any:
    backup_dir = _backup_dir(path)
    if not backup_dir.exists():
        return default
    backups = sorted(backup_dir.glob(f"{path.name}.*.bak"), reverse=True)
    for backup in backups:
        try:
            with backup.open("r", encoding="utf-8") as f:
                data = json.load(f)
            shutil.copy2(backup, path)
            return data
        except (json.JSONDecodeError, OSError):
            continue
    return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        _rotate_backup(path)

    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def _rotate_backup(path: Path) -> None:
    import time

    backup_dir = _backup_dir(path)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    backup_path = backup_dir / f"{path.name}.{stamp}.bak"
    try:
        shutil.copy2(path, backup_path)
    except OSError:
        return

    backups = sorted(backup_dir.glob(f"{path.name}.*.bak"), reverse=True)
    for stale in backups[MAX_BACKUPS:]:
        stale.unlink(missing_ok=True)
