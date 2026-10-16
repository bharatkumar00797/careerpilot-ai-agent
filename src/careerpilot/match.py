"""Deterministic rule-based fit scoring — the floor before any LLM call."""

from __future__ import annotations

import re
from datetime import date

from careerpilot.models import FitReport, JobPosting, Profile, Skill

_TOKEN = re.compile(r"[a-z0-9+#]+")

# Canonical aliases so "ML", "machine learning", "pytorch" overlap sensibly.
_ALIASES: dict[str, str] = {
    "ml": "machine learning",
    "machine-learning": "machine learning",
    "machinelearning": "machine learning",
    "ai": "artificial intelligence",
    "nlp": "natural language processing",
    "cv": "computer vision",
    "k8s": "kubernetes",
    "js": "javascript",
    "ts": "typescript",
    "node": "nodejs",
    "node.js": "nodejs",
    "react.js": "react",
    "reactjs": "react",
    "postgres": "postgresql",
    "golang": "go",
    "py": "python",
    "tf": "tensorflow",
    "torch": "pytorch",
    "llm": "large language models",
    "llms": "large language models",
    "genai": "generative ai",
    "ci/cd": "cicd",
    "ci-cd": "cicd",
    "rest api": "rest",
    "restful": "rest",
    "system design": "system-design",
    "systems design": "system-design",
    "distributed systems": "distributed-systems",
}


def normalize_skill(name: str) -> str:
    key = name.strip().casefold()
    key = key.replace("_", " ").replace("/", " ")
    key = re.sub(r"\s+", " ", key).strip()
    return _ALIASES.get(key, key)


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.casefold()) if len(t) > 1}


def _profile_skill_map(profile: Profile) -> dict[str, Skill]:
    out: dict[str, Skill] = {}
    for skill in profile.skills:
        out[normalize_skill(skill.name)] = skill
    return out


def estimate_years(profile: Profile, *, as_of: date | None = None) -> float:
    """Rough total years of experience from start/end year heuristics."""
    today = as_of or date.today()
    total = 0.0
    for exp in profile.experiences:
        start_year = _year(exp.start)
        end_year = _year(exp.end) if exp.end else today.year
        if start_year is None or end_year is None:
            continue
        span = max(0, end_year - start_year)
        # Treat same-year or ongoing short roles as at least 0.5 years.
        total += max(0.5, float(span)) if span == 0 else float(span)
    return round(min(total, 40.0), 1)


def _year(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(19|20)\d{2}", value)
    return int(match.group(0)) if match else None


def title_overlap(profile: Profile, job: JobPosting) -> float:
    """0-1 overlap between job title tokens and headline / target roles / titles."""
    job_tokens = _tokens(job.title)
    if not job_tokens:
        return 0.0
    cand = " ".join(
        [profile.headline, *profile.target_roles, *(e.title for e in profile.experiences)]
    )
    cand_tokens = _tokens(cand)
    if not cand_tokens:
        return 0.0
    inter = job_tokens & cand_tokens
    return len(inter) / len(job_tokens)


def score_fit(profile: Profile, job: JobPosting) -> FitReport:
    """Produce a deterministic FitReport from skill, title, and experience signals."""
    skill_map = _profile_skill_map(profile)
    reqs = list(job.requirements)
    nice = list(job.nice_to_haves)

    matched: list[str] = []
    missing: list[str] = []
    evidence: list[str] = []
    weighted_hit = 0.0
    weighted_total = 0.0

    for req in reqs:
        weight = 1.0
        weighted_total += weight
        hit = _best_match(normalize_skill(req), skill_map)
        if hit is not None:
            matched.append(hit.name)
            weighted_hit += weight * (hit.level / 5.0)
            evidence.append(
                f"Requirement '{req}' covered by profile skill '{hit.name}' (level {hit.level}/5)."
            )
        else:
            missing.append(req)
            evidence.append(f"Required skill '{req}' not found in the profile skill list.")

    nice_hits = 0
    for item in nice:
        hit = _best_match(normalize_skill(item), skill_map)
        if hit is not None and hit.name not in matched:
            matched.append(hit.name)
            nice_hits += 1
            evidence.append(f"Nice-to-have '{item}' covered by '{hit.name}' (level {hit.level}/5).")

    # Deduplicate matched while preserving order.
    seen: set[str] = set()
    matched_unique: list[str] = []
    for name in matched:
        key = name.casefold()
        if key not in seen:
            seen.add(key)
            matched_unique.append(name)

    skill_score = (weighted_hit / weighted_total * 100.0) if weighted_total else 50.0
    title_score = title_overlap(profile, job) * 100.0
    years = estimate_years(profile)
    # Soft years heuristic: 0-3y -> 40, 3-5 -> 65, 5-8 -> 80, 8+ -> 90.
    if years < 3:
        years_score = 40.0 + years * 8.0
    elif years < 5:
        years_score = 65.0 + (years - 3) * 7.5
    elif years < 8:
        years_score = 80.0 + (years - 5) * 3.0
    else:
        years_score = min(95.0, 90.0 + (years - 8) * 0.5)

    # Blend: skills dominate, title and years add signal.
    raw = 0.65 * skill_score + 0.20 * title_score + 0.15 * years_score
    # Small bonus for nice-to-haves (cap +5).
    raw += min(5.0, nice_hits * 1.5)
    # Penalty for each missing required skill beyond zero.
    if missing:
        raw -= min(25.0, len(missing) * 4.0)
    score = round(max(0.0, min(100.0, raw)))

    coverage = (
        f"{len(matched_unique)} matched / {len(reqs)} required"
        if reqs
        else "no required skills listed"
    )
    summary = (
        f"Rule-based fit score {score}/100 for {profile.name} -> {job.title} at {job.company}. "
        f"Skills: {coverage}. Estimated experience: {years:g} years. "
        f"Title/target overlap: {title_score:.0f}%."
    )
    if missing:
        summary += f" Gaps: {', '.join(missing[:5])}."

    return FitReport(
        score=score,
        matched_skills=matched_unique[:40],
        missing_skills=missing[:40],
        evidence=evidence[:20],
        summary=summary,
    )


def _best_match(req: str, skill_map: dict[str, Skill]) -> Skill | None:
    """Exact canonical match, then substring / token containment."""
    if req in skill_map:
        return skill_map[req]
    req_tokens = _tokens(req)
    best: Skill | None = None
    best_level = -1
    for key, skill in skill_map.items():
        if (req in key or key in req) and skill.level > best_level:
            best = skill
            best_level = skill.level
            continue
        key_tokens = _tokens(key)
        if req_tokens and req_tokens <= key_tokens and skill.level > best_level:
            best = skill
            best_level = skill.level
    return best
