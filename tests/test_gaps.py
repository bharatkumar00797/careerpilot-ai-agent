"""Skill-gap plan tests."""

from __future__ import annotations

from careerpilot.gaps import build_gaps
from careerpilot.match import score_fit
from careerpilot.models import JobPosting, Profile


def test_gaps_for_stretch_role(ml_profile: Profile, product_engineer: JobPosting) -> None:
    fit = score_fit(ml_profile, product_engineer)
    gaps = build_gaps(fit, product_engineer)
    assert gaps
    assert all(g.priority in {"high", "medium", "low"} for g in gaps)
    assert all(g.practice_plan for g in gaps)
    skills = {g.skill.casefold() for g in gaps}
    assert any("react" in s or "typescript" in s for s in skills)


def test_strong_fit_has_few_or_no_gaps(ml_profile: Profile, ml_platform: JobPosting) -> None:
    fit = score_fit(ml_profile, ml_platform)
    gaps = build_gaps(fit, ml_platform)
    assert len(gaps) <= len(fit.missing_skills)
    for gap in gaps:
        assert gap.skill in fit.missing_skills


def test_curated_practice_plan_used_for_python(
    ml_profile: Profile, senior_backend: JobPosting
) -> None:
    fit = score_fit(ml_profile, senior_backend)
    # Force a synthetic missing skill path via copy of fit.
    fit2 = fit.model_copy(update={"missing_skills": ["Python", "Leadership"]})
    gaps = build_gaps(fit2, senior_backend)
    py = next(g for g in gaps if g.skill == "Python")
    assert "mypy" in py.practice_plan or "CLI" in py.practice_plan or "project" in py.practice_plan
