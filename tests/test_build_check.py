from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_check.py"
_spec = importlib.util.spec_from_file_location("build_check", SCRIPT)
build_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_check)


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".gitignore").write_text("node_modules\n/data_raw/\n", encoding="utf-8")
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "data_derived").mkdir()
    (tmp_path / "data_derived" / "meta.json").write_text("{}", encoding="utf-8")
    (tmp_path / "data_raw").mkdir()
    (tmp_path / "data_raw" / "matches.csv").write_text("id\n1\n", encoding="utf-8")
    return tmp_path


def _sparse_file(path: Path, size: int):
    with path.open("wb") as handle:
        handle.seek(size - 1)
        handle.write(b"\0")


def test_clean_repo_passes(tmp_path: Path):
    repo = _repo(tmp_path)
    errors, checked = build_check.check(repo)
    assert errors == []
    assert checked > 0
    assert build_check.main(repo) == 0


def test_raw_filename_outside_data_raw_fails(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / "data_derived" / "matches.csv").write_text("id\n1\n", encoding="utf-8")
    errors, _ = build_check.check(repo)
    assert any("Raw-pack filename outside data_raw" in error for error in errors)


def test_data_raw_path_in_deploy_root_fails(tmp_path: Path):
    repo = _repo(tmp_path)
    nested = repo / "data_derived" / "data_raw"
    nested.mkdir()
    (nested / "notes.txt").write_text("secret\n", encoding="utf-8")
    errors, _ = build_check.check(repo)
    assert any("data_raw path in deploy bundle" in error for error in errors)


def test_oversized_files_only_fail_in_deploy_roots(tmp_path: Path):
    repo = _repo(tmp_path)
    _sparse_file(repo / "backend" / "big.bin", build_check.MAX_BYTES + 1)
    (repo / "docs").mkdir()
    _sparse_file(repo / "docs" / "big.bin", build_check.MAX_BYTES + 1)

    errors, _ = build_check.check(repo)
    oversized = [error for error in errors if "larger than 5 MB" in error]
    assert len(oversized) == 1
    assert "backend" in oversized[0]


def test_gitignore_must_contain_data_raw(tmp_path: Path):
    repo = _repo(tmp_path)
    (repo / ".gitignore").write_text("node_modules\n", encoding="utf-8")
    errors, _ = build_check.check(repo)
    assert any("/data_raw/" in error for error in errors)

    (repo / ".gitignore").unlink()
    errors, _ = build_check.check(repo)
    assert any("/data_raw/" in error for error in errors)


def test_main_reports_failure(tmp_path: Path, capsys):
    repo = _repo(tmp_path)
    (repo / "data_derived" / "teams.csv").write_text("id\n1\n", encoding="utf-8")
    assert build_check.main(repo) == 1
    assert "BUILD CHECK FAILED" in capsys.readouterr().out
