"""Configuration for the HTTP service, loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from careerpilot.config import env_bool, env_int

AccessMode = Literal["api-key", "dev", "public-demo"]


def _env_list(name: str) -> tuple[str, ...]:
    raw = os.getenv(name, "")
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def running_serverless() -> bool:
    """True on serverless platforms where background threads do not outlive a request."""
    return any(os.getenv(name) for name in ("VERCEL", "AWS_LAMBDA_FUNCTION_NAME"))


@dataclass(frozen=True)
class ApiSettings:
    """Service settings.

    Access modes:

    * keys configured (``CAREERPILOT_API_KEYS``) -> every ``/api`` call needs ``X-API-Key`` or a
      Bearer token; callers may submit custom profiles/jobs and use the configured LLM provider.
    * ``dev_mode`` -> no auth and full access; meant for ``localhost`` only.
    * neither -> public demo: anonymous callers may only analyze packaged demos with the offline
      mock provider, and only see their own analyses.

    ``sync_runs`` runs the analysis inside ``POST /api/analyze`` (serverless hosts freeze
    background threads once a response is sent); it is auto-enabled on Vercel / Lambda.
    """

    api_keys: tuple[str, ...] = ()
    dev_mode: bool = False
    cors_origins: tuple[str, ...] = ()
    rate_limit_per_minute: int = 120
    analyze_limit_per_minute: int = 10
    max_concurrent_runs: int = 2
    max_queued_runs: int = 8
    max_analyses_kept: int = 200
    trust_proxy: bool = False
    sync_runs: bool = False

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_keys)

    @property
    def access_mode(self) -> AccessMode:
        if self.auth_enabled:
            return "api-key"
        return "dev" if self.dev_mode else "public-demo"

    @property
    def public_demo(self) -> bool:
        return self.access_mode == "public-demo"

    @classmethod
    def from_env(cls) -> ApiSettings:
        return cls(
            api_keys=_env_list("CAREERPILOT_API_KEYS"),
            dev_mode=env_bool("CAREERPILOT_DEV_MODE", False),
            cors_origins=_env_list("CAREERPILOT_CORS_ORIGINS"),
            rate_limit_per_minute=env_int("CAREERPILOT_RATE_LIMIT_PER_MINUTE", 120),
            analyze_limit_per_minute=env_int("CAREERPILOT_ANALYZE_LIMIT_PER_MINUTE", 10),
            max_concurrent_runs=max(1, env_int("CAREERPILOT_MAX_CONCURRENT_RUNS", 2)),
            max_queued_runs=max(1, env_int("CAREERPILOT_MAX_QUEUED_RUNS", 8)),
            max_analyses_kept=max(10, env_int("CAREERPILOT_MAX_ANALYSES_KEPT", 200)),
            trust_proxy=env_bool("CAREERPILOT_TRUST_PROXY", False),
            sync_runs=env_bool("CAREERPILOT_SYNC_RUNS", running_serverless()),
        )
