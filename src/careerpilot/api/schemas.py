"""Request and response schemas for the HTTP API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from careerpilot.api.jobs import JobState
from careerpilot.models import CareerBrief, JobPosting, Profile


class AnalyzeCreate(BaseModel):
    """Exactly one of (packaged ``profile_id`` + ``job_id``) or (inline ``profile`` + ``job``)."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str | None = Field(
        default=None, min_length=1, max_length=40, pattern=r"^[a-z0-9-]+$"
    )
    job_id: str | None = Field(default=None, min_length=1, max_length=40, pattern=r"^[a-z0-9-]+$")
    profile: Profile | None = None
    job: JobPosting | None = None
    provider: Literal["mock", "configured"] | None = None

    @model_validator(mode="after")
    def _exactly_one_pair(self) -> AnalyzeCreate:
        packaged = self.profile_id is not None and self.job_id is not None
        inline = self.profile is not None and self.job is not None
        half_packaged = (self.profile_id is None) != (self.job_id is None)
        half_inline = (self.profile is None) != (self.job is None)
        if half_packaged or half_inline:
            raise ValueError(
                "profile_id and job_id must be provided together; same for profile/job"
            )
        if packaged == inline:
            raise ValueError("Provide exactly one of (profile_id + job_id) or (profile + job)")
        return self


class EventOut(BaseModel):
    seq: int
    stage: str
    data: dict[str, Any] = Field(default_factory=dict)


class AnalyzeSummaryOut(BaseModel):
    id: str
    state: JobState
    profile_id: str
    job_id: str
    profile_name: str
    job_title: str
    job_company: str
    provider: str
    score: int | None = None
    created_at: datetime
    finished_at: datetime | None = None


class AnalyzeDetailOut(AnalyzeSummaryOut):
    started_at: datetime | None = None
    error: str | None = None
    event_count: int = 0
    brief: CareerBrief | None = None
    simulated: bool = False


class AnalyzeCreatedOut(AnalyzeDetailOut):
    events: list[EventOut] = Field(default_factory=list)


class AnalyzeListOut(BaseModel):
    analyses: list[AnalyzeSummaryOut]


class EventsOut(BaseModel):
    id: str
    state: JobState
    done: bool
    next_cursor: int
    events: list[EventOut]


class ProfileSummaryOut(BaseModel):
    id: str
    name: str
    headline: str
    target_roles: list[str]


class ProfileListOut(BaseModel):
    profiles: list[ProfileSummaryOut]


class JobSummaryOut(BaseModel):
    id: str
    title: str
    company: str
    location: str | None = None


class JobListOut(BaseModel):
    jobs: list[JobSummaryOut]


class ConfigOut(BaseModel):
    version: str
    auth_required: bool
    access_mode: str
    authenticated: bool
    custom_inputs_allowed: bool
    providers: list[str]
    default_provider: str
    sync_runs: bool
    profiles: list[str]
    jobs: list[str]
    simulated: bool = False


class HealthOut(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    active_analyses: int
