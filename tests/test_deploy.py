"""Deployment configs stay consistent with the app: env var names, $PORT, health checks."""

from __future__ import annotations

import importlib.util
import json
import re
import tomllib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from careerpilot.ingest import list_jobs, list_profiles

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "careerpilot"


def _known_env_vars() -> set[str]:
    names: set[str] = set()
    for path in SRC.rglob("*.py"):
        names |= set(re.findall(r'"(CAREERPILOT_[A-Z_]+)"', path.read_text(encoding="utf-8")))
    return names


def _documented_env_vars() -> set[str]:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    return set(re.findall(r"^(CAREERPILOT_[A-Z_]+)=", text, flags=re.MULTILINE))


def test_env_example_documents_every_setting() -> None:
    known = _known_env_vars()
    assert {
        "CAREERPILOT_PROVIDER",
        "CAREERPILOT_API_KEYS",
        "CAREERPILOT_SYNC_RUNS",
        "CAREERPILOT_TRUST_PROXY",
    } <= known
    # Host port is compose-only (not read by app code).
    documented = _documented_env_vars() - {"CAREERPILOT_HOST_PORT"}
    assert known == documented


def test_render_blueprint() -> None:
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "runtime: docker" in text
    assert "healthCheckPath: /healthz" in text
    keys = set(re.findall(r"- key: (\S+)", text))
    assert keys and keys <= _known_env_vars()
    assert "CAREERPILOT_API_KEY\n" not in text


def test_fly_config_matches_port_and_health_check() -> None:
    fly = tomllib.loads((ROOT / "fly.toml").read_text(encoding="utf-8"))
    assert fly["build"]["dockerfile"] == "Dockerfile"
    assert int(fly["env"]["PORT"]) == fly["http_service"]["internal_port"]
    assert set(fly["env"]) - {"PORT"} <= _known_env_vars()
    assert fly["http_service"]["checks"][0]["path"] == "/healthz"


def test_railway_config() -> None:
    railway = json.loads((ROOT / "railway.json").read_text(encoding="utf-8"))
    assert railway["build"]["builder"] == "DOCKERFILE"
    assert railway["deploy"]["healthcheckPath"] == "/healthz"


def test_dockerfile_honours_port() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "${PORT:-8000}" in text and "USER careerpilot" in text and "HEALTHCHECK" in text


def test_vercel_bundles_package_data_and_routes_everything_to_the_app() -> None:
    vercel = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    function = vercel["functions"]["api/index.py"]
    assert function["includeFiles"] == "src/careerpilot/**"
    assert {"source": "/(.*)", "destination": "/api/index"} in vercel["rewrites"]
    assert (SRC / "api" / "static" / "index.html").is_file()
    assert (SRC / "data" / "profiles" / "ml-engineer.json").is_file()


def test_serverless_entrypoint_is_a_sync_public_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "CAREERPILOT_API_KEYS",
        "CAREERPILOT_DEV_MODE",
        "CAREERPILOT_SYNC_RUNS",
        "CAREERPILOT_MAX_CONCURRENT_RUNS",
    ):
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)
    monkeypatch.setenv("VERCEL", "1")
    spec = importlib.util.spec_from_file_location("vercel_entry", ROOT / "api" / "index.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with TestClient(module.app) as client:
        cfg = client.get("/api/config").json()
        assert cfg["access_mode"] == "public-demo"
        assert cfg["sync_runs"] is True
        assert set(cfg["profiles"]) == set(list_profiles())
        assert set(cfg["jobs"]) == set(list_jobs())
        assert "CareerPilot" in client.get("/").text

        resp = client.post(
            "/api/analyze", json={"profile_id": "ml-engineer", "job_id": "ml-platform"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == "finished"
        assert 70 <= body["brief"]["fit"]["score"] <= 95
