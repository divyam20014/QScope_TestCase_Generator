from __future__ import annotations

import json

from app.storage.json_store import read_json, write_json


def test_write_then_read_roundtrip(tmp_path):
    path = tmp_path / "data.json"
    write_json(path, {"a": 1, "b": [1, 2, 3]})
    assert read_json(path) == {"a": 1, "b": [1, 2, 3]}


def test_read_missing_returns_default(tmp_path):
    path = tmp_path / "missing.json"
    assert read_json(path, default={}) == {}


def test_write_creates_backup_on_overwrite(tmp_path):
    path = tmp_path / "data.json"
    write_json(path, {"v": 1})
    write_json(path, {"v": 2})
    backups = list((tmp_path / ".backups").glob("data.json.*.bak"))
    assert len(backups) == 1
    with backups[0].open() as f:
        assert json.load(f) == {"v": 1}


def test_corrupt_file_recovers_from_backup(tmp_path):
    path = tmp_path / "data.json"
    write_json(path, {"v": 1})
    write_json(path, {"v": 2})
    path.write_text("{not valid json", encoding="utf-8")

    recovered = read_json(path, default="fallback")
    assert recovered == {"v": 1}
