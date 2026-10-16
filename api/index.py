"""Serverless entrypoint (Vercel): exposes the CareerPilot FastAPI app as ``app``.

Serverless functions freeze or discard background threads once a response is sent, so analyses
run synchronously inside ``POST /api/analyze`` (``CAREERPILOT_SYNC_RUNS`` is switched on
automatically when ``VERCEL`` is set, and set here as a fallback). Unless API keys are configured
the deployment is a public demo: packaged profiles/jobs and the offline mock provider.

Analyses live in memory per function instance, so the full brief is returned in the POST
response itself.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ.setdefault("CAREERPILOT_SYNC_RUNS", "true")
os.environ.setdefault("CAREERPILOT_MAX_CONCURRENT_RUNS", "1")

from careerpilot.api import create_app  # noqa: E402  (path setup must run first)

app = create_app()
