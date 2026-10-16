"""Deterministic fit-scoring tests."""

from __future__ import annotations

from careerpilot.match import estimate_years, normalize_skill, score_fit, title_overlap
from careerpilot.models import JobPosting, Profile


def test_normalize_aliases() -> None:
    assert normalize_skill("ML") == "machine learning"
    assert normalize_skill("k8s") == "kubernetes"
    assert normalize_skill("Postgres") == "postgresql"


def test_ml_engineer_vs_ml_platform_is_strong(ml_profile: Profile, ml_platform: JobPosting) -> None:
    fit = score_fit(ml_profile, ml_platform)
    assert fit.score >= 70
    assert "Python" in fit.matched_skills or any(
        "python" in s.casefold() for s in fit.matched_skills
    )
    # Kubernetes is only level 2 but present — should match, not miss.
    assert not any(normalize_skill(m) == "kubernetes" for m in fit.missing_skills)


def test_ml_engineer_vs_senior_backend_is_good(
    ml_profile: Profile, senior_backend: JobPosting
) -> None:
    fit = score_fit(ml_profile, senior_backend)
    assert 55 <= fit.score <= 95
    assert "Python" in fit.matched_skills or any(
        "python" in s.casefold() for s in fit.matched_skills
    )
    # System design is a likely gap for this profile.
    assert any("system" in m.casefold() for m in fit.missing_skills)


def test_ml_engineer_vs_product_engineer_is_partial(
    ml_profile: Profile, product_engineer: JobPosting
) -> None:
    fit = score_fit(ml_profile, product_engineer)
    assert fit.score < 55
    assert len(fit.missing_skills) >= 3
    assert any("react" in m.casefold() or "typescript" in m.casefold() for m in fit.missing_skills)


def test_hybrid_vs_product_engineer_is_strong(
    hybrid_profile: Profile, product_engineer: JobPosting
) -> None:
    fit = score_fit(hybrid_profile, product_engineer)
    assert fit.score >= 65


def test_scoring_is_deterministic(ml_profile: Profile, ml_platform: JobPosting) -> None:
    a = score_fit(ml_profile, ml_platform)
    b = score_fit(ml_profile, ml_platform)
    assert a.model_dump() == b.model_dump()


def test_estimate_years_and_title_overlap(ml_profile: Profile, ml_platform: JobPosting) -> None:
    years = estimate_years(ml_profile)
    assert 4.0 <= years <= 12.0
    assert 0.0 < title_overlap(ml_profile, ml_platform) <= 1.0


def test_evidence_mentions_matches_and_gaps(
    ml_profile: Profile, senior_backend: JobPosting
) -> None:
    fit = score_fit(ml_profile, senior_backend)
    assert fit.evidence
    assert fit.summary
    assert 0 <= fit.score <= 100
