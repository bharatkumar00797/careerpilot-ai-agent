"""Strict pydantic models for profiles, jobs, and CareerPilot outputs."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

Str50 = Annotated[str, Field(min_length=1, max_length=50)]
Str80 = Annotated[str, Field(min_length=1, max_length=80)]
Str120 = Annotated[str, Field(min_length=1, max_length=120)]
Str200 = Annotated[str, Field(min_length=1, max_length=200)]
Str500 = Annotated[str, Field(min_length=1, max_length=500)]
Str2000 = Annotated[str, Field(min_length=1, max_length=2000)]
Str4000 = Annotated[str, Field(min_length=1, max_length=4000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Experience(StrictModel):
    title: Str120
    company: Str120
    start: Annotated[str, Field(min_length=4, max_length=10)]
    end: Annotated[str | None, Field(default=None, max_length=10)] = None
    bullets: Annotated[list[Str500], Field(default_factory=list, max_length=12)]


class Skill(StrictModel):
    name: Str80
    level: Annotated[int, Field(ge=1, le=5)]


class Education(StrictModel):
    school: Str120
    degree: Str120
    year: Annotated[str | None, Field(default=None, max_length=10)] = None


class Profile(StrictModel):
    name: Str80
    headline: Str200
    summary: Str2000
    experiences: Annotated[list[Experience], Field(min_length=1, max_length=12)]
    skills: Annotated[list[Skill], Field(min_length=1, max_length=40)]
    education: Annotated[list[Education], Field(default_factory=list, max_length=6)]
    target_roles: Annotated[list[Str120], Field(default_factory=list, max_length=8)]

    @field_validator("skills")
    @classmethod
    def _unique_skill_names(cls, value: list[Skill]) -> list[Skill]:
        seen: set[str] = set()
        for skill in value:
            key = skill.name.casefold()
            if key in seen:
                raise ValueError(f"duplicate skill name: {skill.name}")
            seen.add(key)
        return value


class JobPosting(StrictModel):
    title: Str120
    company: Str120
    location: Annotated[str | None, Field(default=None, max_length=120)] = None
    requirements: Annotated[list[Str200], Field(min_length=1, max_length=30)]
    nice_to_haves: Annotated[list[Str200], Field(default_factory=list, max_length=20)]
    description: Str4000


class FitReport(StrictModel):
    score: Annotated[int, Field(ge=0, le=100)]
    matched_skills: Annotated[list[Str80], Field(default_factory=list, max_length=40)]
    missing_skills: Annotated[list[Str80], Field(default_factory=list, max_length=40)]
    evidence: Annotated[list[Str500], Field(default_factory=list, max_length=20)]
    summary: Str2000


class SkillGap(StrictModel):
    skill: Str80
    priority: Annotated[str, Field(pattern=r"^(high|medium|low)$")]
    why: Str500
    practice_plan: Str2000


class InterviewPack(StrictModel):
    behavioral: Annotated[list[Str500], Field(default_factory=list, max_length=12)]
    technical: Annotated[list[Str500], Field(default_factory=list, max_length=12)]
    suggested_talking_points: Annotated[list[Str500], Field(default_factory=list, max_length=12)]


class CoverSection(StrictModel):
    heading: Str80
    points: Annotated[list[Str500], Field(min_length=1, max_length=6)]


class ApplicationPackage(StrictModel):
    tailored_bullets: Annotated[list[Str500], Field(default_factory=list, max_length=16)]
    cover_outline: Annotated[list[CoverSection], Field(default_factory=list, max_length=6)]
    keywords_to_mirror: Annotated[list[Str80], Field(default_factory=list, max_length=30)]


class CareerBrief(StrictModel):
    profile_name: Str80
    job_title: Str120
    job_company: Str120
    fit: FitReport
    gaps: Annotated[list[SkillGap], Field(default_factory=list, max_length=20)]
    interview: InterviewPack
    application: ApplicationPackage
    security_flags: Annotated[list[Str200], Field(default_factory=list, max_length=20)]
    provider: Str50 = "mock"
