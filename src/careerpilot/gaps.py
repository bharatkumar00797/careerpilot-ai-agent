"""Skill-gap plans from missing required skills + a curated practice map."""

from __future__ import annotations

from careerpilot.match import normalize_skill
from careerpilot.models import FitReport, JobPosting, SkillGap

_PRACTICE: dict[str, str] = {
    "python": (
        "Complete a small CLI or API project; practice typing with mypy; "
        "review the standard library (pathlib, dataclasses, concurrent.futures)."
    ),
    "sql": (
        "Rebuild 10 analytics queries on a sample dataset; practice window "
        "functions and EXPLAIN plans on PostgreSQL."
    ),
    "postgresql": (
        "Model a normalised schema, write migrations, and tune two slow queries "
        "with indexes and EXPLAIN ANALYZE."
    ),
    "system-design": (
        "Sketch end-to-end designs for a URL shortener, a feed, and a job queue; "
        "compare consistency, latency, and failure modes aloud."
    ),
    "distributed-systems": (
        "Study consensus and idempotent consumers; implement a toy outbox or "
        "saga; review failure injection notes for one service you know."
    ),
    "kubernetes": (
        "Deploy a sample app with Deployment/Service/Ingress; practice "
        "rollouts, probes, and resource limits on a local cluster."
    ),
    "docker": (
        "Write a multi-stage Dockerfile, compose a two-service stack, and "
        "verify a non-root, read-only runtime."
    ),
    "aws": (
        "Build a small VPC + ECS/Lambda + RDS diagram; practise IAM least "
        "privilege and cost tags on a free-tier account."
    ),
    "leadership": (
        "Lead one design review and one retro; write a short RFC; coach a "
        "peer through a debugging session and capture outcomes."
    ),
    "machine learning": (
        "Ship an end-to-end training notebook with evaluation metrics; "
        "document data leakage checks and a simple serving path."
    ),
    "pytorch": (
        "Reproduce a baseline model, add a custom Dataset/DataLoader, and "
        "profile one training step for memory and speed."
    ),
    "tensorflow": (
        "Train a small classifier with tf.data; export SavedModel; serve via "
        "a minimal FastAPI wrapper."
    ),
    "large language models": (
        "Build a retrieval-augmented Q&A over a private corpus; measure "
        "faithfulness; add prompt-injection wrapping around untrusted text."
    ),
    "fastapi": (
        "Implement CRUD + auth + OpenAPI for a small domain; add pydantic "
        "extra=forbid models and a pytest suite."
    ),
    "react": (
        "Build a dashboard with fetch + loading/error states; add accessible "
        "forms; keep DOM writes via textContent only where security matters."
    ),
    "typescript": (
        "Convert a JS module to strict TypeScript; add discriminated unions "
        "and eliminate any; wire eslint + tsc in CI."
    ),
    "product management": (
        "Write a one-pager PRD with problem, metrics, and anti-goals; run a "
        "scoping workshop; ship a measured experiment."
    ),
    "cicd": (
        "Author a GitHub Actions workflow with lint, type-check, tests, and "
        "a deploy gate; add caching and matrix builds."
    ),
    "observability": (
        "Add structured logs, RED metrics, and a sample trace; write a runbook "
        "for the top failure mode."
    ),
    "go": (
        "Implement an HTTP service with context timeouts and table-driven "
        "tests; practise interfaces over concrete types."
    ),
}


def _priority_for(index: int, total: int) -> str:
    if index < max(1, total // 3):
        return "high"
    if index < max(2, (2 * total) // 3):
        return "medium"
    return "low"


def build_gaps(fit: FitReport, job: JobPosting) -> list[SkillGap]:
    """Map missing required skills to prioritised SkillGap entries."""
    gaps: list[SkillGap] = []
    missing = list(fit.missing_skills)
    total = len(missing) or 1
    for i, skill in enumerate(missing):
        key = normalize_skill(skill)
        plan = _PRACTICE.get(key)
        if plan is None:
            # Try first token / shorter key.
            for alias, text in _PRACTICE.items():
                if alias in key or key in alias:
                    plan = text
                    break
        if plan is None:
            plan = (
                f"Study core concepts for '{skill}', build a small project that "
                f"exercises it, and collect two concrete stories for interviews."
            )
        why = (
            f"Listed as a requirement for {job.title} at {job.company}, "
            f"and not present in the profile skill list."
        )
        gaps.append(
            SkillGap(
                skill=skill,
                priority=_priority_for(i, total),
                why=why,
                practice_plan=plan,
            )
        )
    return gaps[:20]
