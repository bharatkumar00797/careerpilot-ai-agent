"""Model validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from careerpilot.models import Experience, JobPosting, Profile, Skill


def test_profile_accepts_valid_payload() -> None:
    profile = Profile(
        name="Ada",
        headline="Engineer",
        summary="Builds things.",
        experiences=[
            Experience(
                title="Engineer",
                company="Acme",
                start="2020",
                bullets=["Shipped X"],
            )
        ],
        skills=[Skill(name="Python", level=4)],
        education=[],
        target_roles=["Backend Engineer"],
    )
    assert profile.name == "Ada"


def test_profile_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Profile(
            name="Ada",
            headline="Engineer",
            summary="Builds things.",
            experiences=[Experience(title="E", company="C", start="2020", bullets=["b"])],
            skills=[Skill(name="Python", level=3)],
            unexpected="nope",  # type: ignore[call-arg]
        )


def test_skill_level_bounds() -> None:
    with pytest.raises(ValidationError):
        Skill(name="Python", level=0)
    with pytest.raises(ValidationError):
        Skill(name="Python", level=6)


def test_duplicate_skill_names_rejected() -> None:
    with pytest.raises(ValidationError):
        Profile(
            name="Ada",
            headline="Engineer",
            summary="Builds things.",
            experiences=[Experience(title="E", company="C", start="2020", bullets=["b"])],
            skills=[Skill(name="Python", level=3), Skill(name="python", level=4)],
        )


def test_job_requires_requirements() -> None:
    with pytest.raises(ValidationError):
        JobPosting(
            title="Eng",
            company="Co",
            requirements=[],
            description="A role.",
        )


def test_string_length_caps() -> None:
    with pytest.raises(ValidationError):
        Skill(name="x" * 81, level=3)
