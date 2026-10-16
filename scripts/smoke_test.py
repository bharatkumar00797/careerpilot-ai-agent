#!/usr/bin/env python3
"""End-to-end smoke test against a running server (stdlib only).

Usage: python3 scripts/smoke_test.py [BASE_URL] [--api-key KEY]

Checks health, the dashboard and its security headers, then runs packaged demo pairs through
the API (works with background and sync mode) and checks fit scores land in expected bands.
Exits non-zero on the first failure.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

# Expected mock score bands for packaged demo pairs.
EXPECTED: list[tuple[str, str, int, int]] = [
    ("ml-engineer", "ml-platform", 70, 95),
    ("fullstack-pm-hybrid", "product-engineer", 65, 100),
]


class Client:
    def __init__(self, base: str, api_key: str | None) -> None:
        self.base = base.rstrip("/")
        self.api_key = api_key

    def request(self, method: str, path: str, body: Any = None) -> tuple[int, Any, Any]:
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.api_key:
            req.add_header("X-API-Key", self.api_key)
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                raw = res.read().decode()
                status, headers = res.status, res.headers
        except urllib.error.HTTPError as err:
            raw, status, headers = err.read().decode(), err.code, err.headers
        ctype = headers.get("content-type", "")
        return status, (json.loads(raw) if "json" in ctype else raw), headers


def check(cond: bool, message: str) -> None:
    if not cond:
        print(f"FAIL {message}")
        sys.exit(1)


def run_pair(c: Client, profile_id: str, job_id: str, lo: int, hi: int) -> None:
    label = f"{profile_id}x{job_id}"
    status, body, _ = c.request(
        "POST", "/api/analyze", {"profile_id": profile_id, "job_id": job_id}
    )
    check(status in (200, 202), f"{label}: create returned {status}: {body}")
    aid = body["id"]
    deadline = time.monotonic() + 60
    while body["state"] not in ("finished", "error"):
        check(time.monotonic() < deadline, f"{label}: analysis timed out")
        time.sleep(0.3)
        _, body, _ = c.request("GET", f"/api/analyze/{aid}")
    check(body["state"] == "finished", f"{label}: state {body['state']} {body.get('error')}")
    score = body["brief"]["fit"]["score"]
    check(lo <= score <= hi, f"{label}: score {score} not in [{lo}, {hi}]")
    status, events, _ = c.request("GET", f"/api/analyze/{aid}/events?since=0")
    check(status == 200 and events["events"], f"{label}: no progress events")
    status, md, _ = c.request("GET", f"/api/analyze/{aid}/brief.md")
    check(status == 200 and "#" in md, f"{label}: brief markdown missing")
    print(f"PASS {label} -> {score}/100")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base", nargs="?", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default=None)
    args = parser.parse_args()
    c = Client(args.base, args.api_key)

    status, health, _ = c.request("GET", "/healthz")
    check(status == 200 and health.get("status") == "ok", f"healthz returned {status}")
    status, page, headers = c.request("GET", "/")
    check(status == 200 and "CareerPilot" in page, "dashboard did not render")
    check("script-src 'self'" in headers.get("content-security-policy", ""), "CSP missing")
    check(headers.get("x-frame-options") == "DENY", "X-Frame-Options missing")
    print(f"PASS health + dashboard (version {health['version']})")

    _, cfg, _ = c.request("GET", "/api/config")
    for profile_id, job_id, _, _ in EXPECTED:
        check(profile_id in cfg["profiles"], f"profile not served: {profile_id}")
        check(job_id in cfg["jobs"], f"job not served: {job_id}")

    if cfg.get("auth_required") and not args.api_key:
        status, _, _ = c.request(
            "POST", "/api/analyze", {"profile_id": "ml-engineer", "job_id": "ml-platform"}
        )
        check(status == 401, f"expected 401 without API key, got {status}")
        print("PASS API-key mode rejects unauthenticated analyze")
        return 0

    for profile_id, job_id, lo, hi in EXPECTED:
        run_pair(c, profile_id, job_id, lo, hi)
    print(f"ALL PASS ({len(EXPECTED) + 1})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
