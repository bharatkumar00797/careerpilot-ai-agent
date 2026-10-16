from __future__ import annotations

import json
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from careerpilot.api import create_app
from careerpilot.api.security import ApiKeyAuth, RateLimiter
from careerpilot.api.settings import ApiSettings
from careerpilot.config import Settings
from careerpilot.ingest import load_profile

DEV = ApiSettings(dev_mode=True, sync_runs=True)


def client(settings: ApiSettings = DEV, **kwargs: Any) -> TestClient:
    return TestClient(create_app(settings, Settings(), **kwargs))


def custom_profile() -> dict[str, Any]:
    data = load_profile("ml-engineer").model_dump()
    data["name"] = "Custom Candidate"
    return data


def custom_job() -> dict[str, Any]:
    from careerpilot.ingest import load_job

    data = load_job("ml-platform").model_dump()
    data["title"] = "Custom ML Role"
    return data


def test_healthz_and_config() -> None:
    c = client()
    health = c.get("/healthz").json()
    assert health["status"] == "ok"
    cfg = c.get("/api/config").json()
    assert cfg["access_mode"] == "dev"
    assert cfg["custom_inputs_allowed"] is True
    assert "ml-engineer" in cfg["profiles"]
    assert "ml-platform" in cfg["jobs"]
    assert "api_key" not in cfg
    assert "CAREERPILOT_API_KEY" not in str(cfg)


def test_openapi_lists_analyze_routes() -> None:
    paths = client().get("/openapi.json").json()["paths"]
    assert "/api/analyze" in paths
    assert "/api/analyze/{analyze_id}/events" in paths
    assert "/api/analyze/{analyze_id}/brief.md" in paths


def test_profiles_and_jobs() -> None:
    c = client()
    ids = [p["id"] for p in c.get("/api/profiles").json()["profiles"]]
    assert "fullstack-pm-hybrid" in ids
    assert c.get("/api/profiles/ml-engineer").json()["name"]
    assert c.get("/api/profiles/nope").status_code == 404
    jobs = [j["id"] for j in c.get("/api/jobs").json()["jobs"]]
    assert "product-engineer" in jobs
    assert c.get("/api/jobs/ml-platform").json()["title"]
    assert c.get("/api/jobs/nope").status_code == 404


def test_sync_analyze_returns_brief_and_events() -> None:
    res = client().post("/api/analyze", json={"profile_id": "ml-engineer", "job_id": "ml-platform"})
    assert res.status_code == 200
    body = res.json()
    assert body["state"] == "finished"
    assert 70 <= body["brief"]["fit"]["score"] <= 95
    assert body["events"] and body["events"][0]["stage"] == "validate"


def test_brief_markdown_and_events_cursor() -> None:
    c = client()
    created = c.post(
        "/api/analyze", json={"profile_id": "ml-engineer", "job_id": "senior-backend"}
    ).json()
    aid = created["id"]
    page = c.get(f"/api/analyze/{aid}/events", params={"since": 0}).json()
    assert page["done"] is True
    assert page["next_cursor"] == len(page["events"]) == created["event_count"]
    tail = c.get(f"/api/analyze/{aid}/events", params={"since": page["next_cursor"]}).json()
    assert tail["events"] == []
    md = c.get(f"/api/analyze/{aid}/brief.md")
    assert md.headers["content-type"].startswith("text/markdown")
    assert "Fit score" in md.text or "fit" in md.text.lower()
    assert c.get("/api/analyze").json()["analyses"][0]["id"] == aid


def test_hybrid_product_engineer_score_band() -> None:
    res = client().post(
        "/api/analyze",
        json={"profile_id": "fullstack-pm-hybrid", "job_id": "product-engineer"},
    )
    assert res.status_code == 200
    assert res.json()["brief"]["fit"]["score"] >= 65


def test_async_mode_returns_202_then_finishes() -> None:
    c = client(ApiSettings(dev_mode=True))
    with c:
        res = c.post("/api/analyze", json={"profile_id": "ml-engineer", "job_id": "ml-platform"})
        assert res.status_code == 202
        aid = res.json()["id"]
        detail = None
        for _ in range(100):
            detail = c.get(f"/api/analyze/{aid}").json()
            if detail["state"] == "finished":
                break
            time.sleep(0.05)
        assert detail is not None
        assert detail["brief"]["fit"]["score"] >= 70


def test_custom_inputs_in_dev_mode() -> None:
    res = client().post("/api/analyze", json={"profile": custom_profile(), "job": custom_job()})
    assert res.status_code == 200
    assert res.json()["profile_id"] == "custom"
    assert res.json()["brief"]["profile_name"] == "Custom Candidate"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"profile_id": "ml-engineer"},
        {"profile_id": "ml-engineer", "job_id": "ml-platform", "profile": {"name": "x"}},
        {"profile_id": "does-not-exist", "job_id": "ml-platform"},
        {"profile_id": "ml-engineer", "job_id": "does-not-exist"},
        {"profile_id": "ml-engineer", "job_id": "ml-platform", "unexpected": 1},
    ],
)
def test_invalid_requests_are_rejected(payload: dict[str, Any]) -> None:
    assert client().post("/api/analyze", json=payload).status_code == 422


def test_public_demo_restrictions_and_ownership() -> None:
    c = client(ApiSettings(sync_runs=True))
    assert c.get("/api/config").json()["access_mode"] == "public-demo"
    assert c.get("/api/config").json()["simulated"] is True
    assert (
        c.post("/api/analyze", json={"profile": custom_profile(), "job": custom_job()}).status_code
        == 403
    )
    res = c.post(
        "/api/analyze",
        json={"profile_id": "ml-engineer", "job_id": "ml-platform", "provider": "configured"},
    )
    assert res.status_code == 403
    ok = c.post("/api/analyze", json={"profile_id": "ml-engineer", "job_id": "ml-platform"})
    assert ok.status_code == 200 and ok.json()["provider"] == "mock"
    assert ok.json()["simulated"] is True
    aid = ok.json()["id"]
    other = TestClient(c.app, client=("203.0.113.9", 5000))
    assert other.get(f"/api/analyze/{aid}").status_code == 404
    assert other.get("/api/analyze").json()["analyses"] == []


def test_api_key_mode() -> None:
    c = client(ApiSettings(api_keys=("s3cret-key",), sync_runs=True))
    assert c.get("/healthz").status_code == 200
    assert c.get("/api/profiles").status_code == 401
    assert c.get("/api/profiles", headers={"X-API-Key": "wrong"}).status_code == 401
    assert c.get("/api/profiles", headers={"X-API-Key": "s3cret-key"}).status_code == 200
    bearer = {"Authorization": "Bearer s3cret-key"}
    res = c.post(
        "/api/analyze", json={"profile": custom_profile(), "job": custom_job()}, headers=bearer
    )
    assert res.status_code == 200
    assert c.get("/api/config", headers=bearer).json()["authenticated"] is True


def test_general_rate_limit() -> None:
    c = client(ApiSettings(dev_mode=True, rate_limit_per_minute=3))
    codes = [c.get("/api/profiles").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]


def test_analyze_rate_limit_counts_only_valid_requests() -> None:
    c = client(ApiSettings(dev_mode=True, sync_runs=True, analyze_limit_per_minute=1))
    assert (
        c.post("/api/analyze", json={"profile_id": "bad-id", "job_id": "ml-platform"}).status_code
        == 422
    )
    assert (
        c.post(
            "/api/analyze", json={"profile_id": "ml-engineer", "job_id": "ml-platform"}
        ).status_code
        == 200
    )
    res = c.post("/api/analyze", json={"profile_id": "ml-engineer", "job_id": "ml-platform"})
    assert res.status_code == 429 and "retry-after" in res.headers


def test_body_limit() -> None:
    big = json.dumps({"profile_id": "ml-engineer", "job_id": "ml-platform", "pad": "x" * 70_000})
    res = client().post("/api/analyze", content=big, headers={"Content-Type": "application/json"})
    assert res.status_code == 413


def test_security_headers_and_dashboard() -> None:
    c = client()
    page = c.get("/")
    assert page.status_code == 200 and "CareerPilot" in page.text
    csp = page.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp
    assert page.headers["x-frame-options"] == "DENY"
    assert c.get("/api/profiles").headers["cache-control"] == "no-store"
    assert c.get("/static/app.js").status_code == 200
    assert "innerHTML" not in c.get("/static/app.js").text


def test_crashing_run_is_reported_as_error() -> None:
    def boom(*_: Any) -> Any:
        raise RuntimeError("provider exploded")

    res = client(run_fn=boom).post(
        "/api/analyze", json={"profile_id": "ml-engineer", "job_id": "ml-platform"}
    )
    assert res.status_code == 200
    assert res.json()["state"] == "error" and "exploded" in res.json()["error"]


def test_queue_full_returns_503() -> None:
    import threading

    gate = threading.Event()

    def slow(profile: Any, job: Any, settings: Any, hook: Any) -> Any:
        gate.wait(5)
        raise RuntimeError("stopped")

    c = client(ApiSettings(dev_mode=True, max_queued_runs=1), run_fn=slow)
    with c:
        assert (
            c.post(
                "/api/analyze", json={"profile_id": "ml-engineer", "job_id": "ml-platform"}
            ).status_code
            == 202
        )
        res = c.post("/api/analyze", json={"profile_id": "ml-engineer", "job_id": "ml-platform"})
        assert res.status_code == 503
        gate.set()


def test_api_key_auth_and_rate_limiter_units() -> None:
    auth = ApiKeyAuth(("a", "b"))
    assert auth.enabled and auth.verify("b") and auth.verify("c") is None
    assert auth.verify(None) is None
    now = [0.0]
    limiter = RateLimiter(2, 10, clock=lambda: now[0])
    assert limiter.check("x") is None and limiter.check("x") is None
    assert limiter.check("x") == pytest.approx(10)
    now[0] = 10.5
    assert limiter.check("x") is None


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAREERPILOT_API_KEYS", "k1, k2")
    monkeypatch.setenv("VERCEL", "1")
    s = ApiSettings.from_env()
    assert s.api_keys == ("k1", "k2") and s.access_mode == "api-key" and s.sync_runs


def test_cli_serve_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    import uvicorn

    from careerpilot import cli

    seen: dict[str, Any] = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: seen.update(kw))
    monkeypatch.setenv("PORT", "9123")
    assert cli.main(["serve", "--dev"]) == 0
    assert seen["port"] == 9123 and seen["host"] == "127.0.0.1"


def test_right_most_xff_behind_trust_proxy() -> None:
    from starlette.requests import Request

    from careerpilot.api.app import client_ip

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(b"x-forwarded-for", b"1.1.1.1, 2.2.2.2, 3.3.3.3")],
        "client": ("9.9.9.9", 123),
        "server": ("test", 80),
    }
    req = Request(scope)
    assert client_ip(req, trust_proxy=True) == "3.3.3.3"
    assert client_ip(req, trust_proxy=False) == "9.9.9.9"
