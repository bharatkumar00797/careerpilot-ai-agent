"""CareerPilot pipeline: validate → wrap → rule match → enrich → assemble."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from careerpilot.config import Settings
from careerpilot.gaps import build_gaps
from careerpilot.ingest import scan_job, scan_profile, wrap_job, wrap_profile
from careerpilot.llm import MockProvider, build_provider
from careerpilot.llm.base import LLMProvider
from careerpilot.llm.mock import MockProvider as MockEnricher
from careerpilot.match import score_fit
from careerpilot.models import (
    ApplicationPackage,
    CareerBrief,
    CoverSection,
    FitReport,
    InterviewPack,
    JobPosting,
    Profile,
    SkillGap,
)

ProgressHook = Callable[[str, dict[str, Any]], None]


class CareerPilot:
    """End-to-end career analysis engine."""

    def __init__(
        self,
        provider: LLMProvider | None = None,
        *,
        settings: Settings | None = None,
        on_progress: ProgressHook | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.provider = provider or build_provider(self.settings)
        self.on_progress = on_progress

    def _emit(self, step: str, **payload: Any) -> None:
        if self.on_progress is not None:
            self.on_progress(step, payload)

    def analyze(self, profile: Profile, job: JobPosting) -> CareerBrief:
        """Run the full pipeline and return a CareerBrief."""
        self._emit("validate", profile=profile.name, job=job.title)

        flags = scan_profile(profile) + scan_job(job)
        # Wrapping is for LLM prompts; side effect documents that we treat text as data.
        _ = wrap_profile(profile.summary)
        _ = wrap_job(job.description)
        self._emit("wrap_untrusted", flags=len(flags))

        fit = score_fit(profile, job)
        self._emit("rule_match", score=fit.score)

        gaps = build_gaps(fit, job)
        self._emit("gaps", count=len(gaps))

        fit, gaps, interview, application = self._enrich(profile, job, fit, gaps)
        self._emit("enrich", provider=self.provider.name)

        brief = CareerBrief(
            profile_name=profile.name,
            job_title=job.title,
            job_company=job.company,
            fit=fit,
            gaps=gaps,
            interview=interview,
            application=application,
            security_flags=flags[:20],
            provider=self.provider.name,
        )
        self._emit("assemble", score=brief.fit.score)
        return brief

    def _enrich(
        self,
        profile: Profile,
        job: JobPosting,
        fit: FitReport,
        gaps: list[SkillGap],
    ) -> tuple[FitReport, list[SkillGap], InterviewPack, ApplicationPackage]:
        provider = self.provider
        if isinstance(provider, MockProvider):
            return provider.enrich(profile, job, fit, gaps)
        # Non-mock: still use deterministic templates for structured packs so the
        # product works without relying on free-form JSON from a remote model.
        # Remote complete() is available for future narration hooks; for S1 we
        # keep structured outputs rule/mock-derived so scoring stays honest.
        enricher = MockEnricher()
        return enricher.enrich(profile, job, fit, gaps)


def analyze(
    profile: Profile,
    job: JobPosting,
    *,
    provider: LLMProvider | None = None,
    settings: Settings | None = None,
) -> CareerBrief:
    """Module-level convenience wrapper around CareerPilot.analyze."""
    return CareerPilot(provider=provider, settings=settings).analyze(profile, job)


def brief_to_markdown(brief: CareerBrief) -> str:
    """Render a CareerBrief as readable Markdown."""
    lines: list[str] = [
        f"# Career brief: {brief.profile_name} → {brief.job_title} @ {brief.job_company}",
        "",
        f"**Provider:** {brief.provider}  ",
        f"**Fit score:** {brief.fit.score}/100",
        "",
        "## Summary",
        brief.fit.summary,
        "",
        "### Matched skills",
        ", ".join(brief.fit.matched_skills) or "_(none)_",
        "",
        "### Missing skills",
        ", ".join(brief.fit.missing_skills) or "_(none)_",
        "",
        "### Evidence",
    ]
    for item in brief.fit.evidence:
        lines.append(f"- {item}")
    lines += ["", "## Skill gaps"]
    if not brief.gaps:
        lines.append("_No required-skill gaps._")
    for gap in brief.gaps:
        lines += [
            f"### {gap.skill} ({gap.priority})",
            f"**Why:** {gap.why}",
            f"**Practice:** {gap.practice_plan}",
            "",
        ]
    lines += ["## Interview pack", "### Behavioural"]
    for q in brief.interview.behavioral:
        lines.append(f"- {q}")
    lines.append("### Technical")
    for q in brief.interview.technical:
        lines.append(f"- {q}")
    lines.append("### Talking points")
    for q in brief.interview.suggested_talking_points:
        lines.append(f"- {q}")
    lines += ["", "## Application package", "### Tailored bullets"]
    for b in brief.application.tailored_bullets:
        lines.append(f"- {b}")
    lines.append("### Cover outline")
    for section in brief.application.cover_outline:
        lines.append(f"#### {section.heading}")
        for point in section.points:
            lines.append(f"- {point}")
    lines += [
        "",
        "### Keywords to mirror",
        ", ".join(brief.application.keywords_to_mirror) or "_(none)_",
    ]
    if brief.security_flags:
        lines += ["", "## Security flags"]
        for flag in brief.security_flags:
            lines.append(f"- {flag}")
    lines.append("")
    return "\n".join(lines)


def empty_application() -> ApplicationPackage:
    return ApplicationPackage(
        tailored_bullets=[],
        cover_outline=[CoverSection(heading="Opening", points=["TBD"])],
        keywords_to_mirror=[],
    )
