"""CLI smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from careerpilot import __version__
from careerpilot.cli import main


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_profiles_and_jobs(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["profiles"]) == 0
    out = capsys.readouterr().out
    assert "ml-engineer" in out
    assert main(["jobs"]) == 0
    assert "ml-platform" in capsys.readouterr().out


def test_match_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["match", "ml-engineer", "ml-platform", "--json", "--provider", "mock"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert "score" in data
    assert data["score"] >= 70


def test_analyze_writes_out_dir(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "brief"
    assert (
        main(
            [
                "analyze",
                "ml-engineer",
                "senior-backend",
                "--provider",
                "mock",
                "--out",
                str(out),
            ]
        )
        == 0
    )
    assert (out / "brief.md").is_file()
    assert (out / "brief.json").is_file()
    payload = json.loads((out / "brief.json").read_text(encoding="utf-8"))
    assert payload["fit"]["score"] >= 50
    assert "Wrote" in capsys.readouterr().out


def test_prep_and_package(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["prep", "ml-engineer", "ml-platform", "--json"]) == 0
    prep = json.loads(capsys.readouterr().out)
    assert prep["behavioral"] and prep["technical"]
    assert main(["package", "fullstack-pm-hybrid", "product-engineer", "--json"]) == 0
    pkg = json.loads(capsys.readouterr().out)
    assert pkg["tailored_bullets"] and pkg["cover_outline"]
