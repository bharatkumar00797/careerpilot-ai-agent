"""Load, validate, and sanitize career profiles and job postings."""

from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path
from typing import Any

from careerpilot.models import JobPosting, Profile

_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "override-instructions",
        re.compile(
            r"\b(ignore|disregard|forget)\b.{0,40}\b(previous|prior|above|all)\b"
            r".{0,30}\b(instructions?|rules|prompts?)",
            re.I | re.S,
        ),
    ),
    (
        "role-hijack",
        re.compile(
            r"\byou are now\b|\bact as (the )?(system|admin|developer)\b|\bnew instructions\b",
            re.I,
        ),
    ),
    (
        "score-manipulation",
        re.compile(
            r"\b(always|must|only)\b.{0,30}\b(score|rate|rank|match)\b.{0,40}\b"
            r"(100|perfect|hire|yes)\b",
            re.I | re.S,
        ),
    ),
    (
        "prompt-exfiltration",
        re.compile(
            r"\b(reveal|print|show|repeat)\b.{0,30}\b(system prompt|instructions|api key|secret)",
            re.I | re.S,
        ),
    ),
    ("fake-delimiter", re.compile(r"</?\s*(untrusted|system|assistant|profile|job)[^>]*>", re.I)),
)

PROFILE_OPEN = "<untrusted-profile>"
PROFILE_CLOSE = "</untrusted-profile>"
JOB_OPEN = "<untrusted-job>"
JOB_CLOSE = "</untrusted-job>"

_MAX_RAW_BYTES = 256_000


def sanitize_text(text: str, *, max_length: int = 4000) -> str:
    """Strip control characters and hard-cap length."""
    cleaned = _CONTROL.sub("", str(text))
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned[:max_length]


def neutralize(text: str) -> str:
    """Defang delimiter look-alikes so untrusted text cannot close a data block."""
    return re.sub(
        r"<(/?)\s*(untrusted|system|assistant|profile|job)",
        r"[\1\2",
        text,
        flags=re.I,
    )


def wrap_profile(text: str) -> str:
    return f"{PROFILE_OPEN}\n{neutralize(sanitize_text(text))}\n{PROFILE_CLOSE}"


def wrap_job(text: str) -> str:
    return f"{JOB_OPEN}\n{neutralize(sanitize_text(text))}\n{JOB_CLOSE}"


def scan_text(text: str) -> list[str]:
    return [name for name, pattern in _INJECTION_PATTERNS if pattern.search(text)]


def scan_profile(profile: Profile) -> list[str]:
    fields: list[tuple[str, str]] = [
        ("name", profile.name),
        ("headline", profile.headline),
        ("summary", profile.summary),
    ]
    for i, exp in enumerate(profile.experiences):
        fields.append((f"experiences[{i}].title", exp.title))
        fields.append((f"experiences[{i}].company", exp.company))
        for j, bullet in enumerate(exp.bullets):
            fields.append((f"experiences[{i}].bullets[{j}]", bullet))
    for i, skill in enumerate(profile.skills):
        fields.append((f"skills[{i}].name", skill.name))
    for i, role in enumerate(profile.target_roles):
        fields.append((f"target_roles[{i}]", role))
    return _findings(fields)


def scan_job(job: JobPosting) -> list[str]:
    fields: list[tuple[str, str]] = [
        ("title", job.title),
        ("company", job.company),
        ("description", job.description),
    ]
    if job.location:
        fields.append(("location", job.location))
    for i, req in enumerate(job.requirements):
        fields.append((f"requirements[{i}]", req))
    for i, nice in enumerate(job.nice_to_haves):
        fields.append((f"nice_to_haves[{i}]", nice))
    return _findings(fields)


def _findings(fields: list[tuple[str, str]]) -> list[str]:
    out: list[str] = []
    for where, text in fields:
        for name in scan_text(text):
            out.append(f"{name} pattern in {where} (treated as data, not instructions)")
    return out


def _data_root() -> Path:
    base = resources.files("careerpilot") / "data"
    return Path(str(base))


def list_profiles() -> list[str]:
    root = _data_root() / "profiles"
    return sorted(p.stem for p in root.glob("*.json"))


def list_jobs() -> list[str]:
    root = _data_root() / "jobs"
    return sorted(p.stem for p in root.glob("*.json"))


def load_profile(name_or_path: str) -> Profile:
    data = _load_json(name_or_path, kind="profiles")
    return Profile.model_validate(_sanitize_mapping(data))


def load_job(name_or_path: str) -> JobPosting:
    data = _load_json(name_or_path, kind="jobs")
    return JobPosting.model_validate(_sanitize_mapping(data))


def parse_profile_json(raw: str | bytes | dict[str, Any]) -> Profile:
    data = _coerce_json(raw)
    return Profile.model_validate(_sanitize_mapping(data))


def parse_job_json(raw: str | bytes | dict[str, Any]) -> JobPosting:
    data = _coerce_json(raw)
    return JobPosting.model_validate(_sanitize_mapping(data))


def _coerce_json(raw: str | bytes | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, bytes):
        if len(raw) > _MAX_RAW_BYTES:
            raise ValueError(f"payload exceeds {_MAX_RAW_BYTES} bytes")
        text = raw.decode("utf-8")
    else:
        if len(raw) > _MAX_RAW_BYTES:
            raise ValueError(f"payload exceeds {_MAX_RAW_BYTES} bytes")
        text = raw
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


def _load_json(name_or_path: str, *, kind: str) -> dict[str, Any]:
    path = Path(name_or_path)
    if path.suffix == ".json" and path.is_file():
        raw = path.read_bytes()
        if len(raw) > _MAX_RAW_BYTES:
            raise ValueError(f"file exceeds {_MAX_RAW_BYTES} bytes")
        data = json.loads(raw.decode("utf-8"))
    else:
        packaged = _data_root() / kind / f"{name_or_path}.json"
        if not packaged.is_file():
            available = list_profiles() if kind == "profiles" else list_jobs()
            raise FileNotFoundError(
                f"unknown {kind[:-1]} {name_or_path!r}; available: {', '.join(available)}"
            )
        data = json.loads(packaged.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


def _sanitize_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively sanitize string leaves before pydantic validation."""

    def walk(value: Any) -> Any:
        if isinstance(value, str):
            return sanitize_text(value, max_length=4000)
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        return value

    out = walk(data)
    assert isinstance(out, dict)
    return out
