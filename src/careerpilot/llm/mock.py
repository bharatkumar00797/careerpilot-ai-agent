"""Deterministic offline enricher used by default, in demos, and in tests.

Narrates from the rule-based FitReport and facts already present in the profile
or job description. Never invents employer names, metrics, or skills outside
the allowlisted sets.
"""

from __future__ import annotations

from careerpilot.llm.base import Completion, LLMProvider, Message, Usage
from careerpilot.match import normalize_skill
from careerpilot.models import (
    ApplicationPackage,
    CoverSection,
    FitReport,
    InterviewPack,
    JobPosting,
    Profile,
    SkillGap,
)


class MockProvider(LLMProvider):
    name = "mock"

    def complete(self, messages: list[Message], *, temperature: float = 0.0) -> Completion:
        # Chat surface kept for protocol parity; enrich() is what the engine uses.
        joined = " ".join(m.content for m in messages)
        content = (
            "Mock provider acknowledges the request. "
            "Use CareerPilot.analyze() for structured enrichment."
        )
        return Completion(
            content=content,
            model="mock-careerpilot-1",
            usage=Usage(prompt_tokens=len(joined) // 4, completion_tokens=len(content) // 4),
        )

    def enrich(
        self,
        profile: Profile,
        job: JobPosting,
        fit: FitReport,
        gaps: list[SkillGap],
    ) -> tuple[FitReport, list[SkillGap], InterviewPack, ApplicationPackage]:
        narrated = self._narrate_fit(profile, job, fit)
        interview = self._interview_pack(profile, job, fit)
        application = self._application_package(profile, job, fit)
        return narrated, gaps, interview, application

    def _narrate_fit(self, profile: Profile, job: JobPosting, fit: FitReport) -> FitReport:
        tone = (
            "strong"
            if fit.score >= 75
            else "solid"
            if fit.score >= 55
            else "partial"
            if fit.score >= 35
            else "stretch"
        )
        top_matched = ", ".join(fit.matched_skills[:5]) or "none listed"
        top_missing = ", ".join(fit.missing_skills[:5]) or "none"
        companies = [e.company for e in profile.experiences[:2]]
        company_note = (
            f"Experience cited from {', '.join(companies)} only — no external employers invented."
            if companies
            else "No employer names invented."
        )
        summary = (
            f"{profile.name} is a {tone} fit ({fit.score}/100) for {job.title} at {job.company}. "
            f"Matched skills: {top_matched}. Remaining gaps: {top_missing}. {company_note}"
        )
        # Keep rule evidence; prepend a narrated line restating score + allowlisted skills.
        evidence = [
            f"Narration restates rule score {fit.score}/100 using only profile/JD skills.",
            *fit.evidence,
        ][:20]
        return FitReport(
            score=fit.score,
            matched_skills=fit.matched_skills,
            missing_skills=fit.missing_skills,
            evidence=evidence,
            summary=summary[:2000],
        )

    def _interview_pack(self, profile: Profile, job: JobPosting, fit: FitReport) -> InterviewPack:
        recent = profile.experiences[0]
        matched = fit.matched_skills[:4]
        missing = fit.missing_skills[:3]
        behavioral = [
            f"Tell me about a time at {recent.company} when you owned an outcome end to end.",
            f"Describe a conflict you resolved while working as {recent.title}.",
            f"How would you prioritise learning '{missing[0]}' in your first 90 days?"
            if missing
            else f"How do you decide what to build next in a {job.title} role?",
        ]
        technical = []
        for skill in matched[:3]:
            technical.append(
                f"Walk through how you have used {skill} in production (stick to profile facts)."
            )
        for skill in missing[:2]:
            technical.append(
                f"How would you ramp on {skill} for {job.company}'s {job.title} needs?"
            )
        if not technical:
            technical.append(f"Design a simple component relevant to {job.title}.")
        talking = [
            f"Lead with {profile.headline}.",
            f"Anchor stories in {recent.company} / {recent.title}.",
        ]
        for skill in matched[:3]:
            talking.append(f"Highlight {skill} as a direct requirement match.")
        for gap in missing[:2]:
            talking.append(f"Acknowledge {gap} as a gap with a concrete practice plan.")
        return InterviewPack(
            behavioral=behavioral[:12],
            technical=technical[:12],
            suggested_talking_points=talking[:12],
        )

    def _application_package(
        self, profile: Profile, job: JobPosting, fit: FitReport
    ) -> ApplicationPackage:
        allowlisted = {normalize_skill(s.name) for s in profile.skills} | {
            normalize_skill(s) for s in fit.matched_skills
        }
        bullets: list[str] = []
        for exp in profile.experiences:
            for bullet in exp.bullets:
                # Only keep bullets whose tokens intersect allowlisted/job skills lightly,
                # otherwise keep first bullets as factual profile text (never invent).
                bullets.append(f"[{exp.company}] {bullet}")
                if len(bullets) >= 8:
                    break
            if len(bullets) >= 8:
                break
        if not bullets:
            bullets.append(f"[{profile.name}] {profile.headline}")

        keywords = list(fit.matched_skills[:10])
        for req in job.requirements:
            key = normalize_skill(req)
            if (
                key in allowlisted or any(key in normalize_skill(m) for m in fit.matched_skills)
            ) and req not in keywords:
                keywords.append(req)
            if len(keywords) >= 15:
                break
        # Mirror JD keywords that already appear in profile skills only.
        for req in job.requirements + job.nice_to_haves:
            ns = normalize_skill(req)
            if ns in {normalize_skill(s.name) for s in profile.skills} and req not in keywords:
                keywords.append(req)
            if len(keywords) >= 20:
                break

        cover = [
            CoverSection(
                heading="Opening",
                points=[
                    f"I am applying for {job.title} at {job.company}.",
                    f"My background: {profile.headline}.",
                ],
            ),
            CoverSection(
                heading="Relevant experience",
                points=[f"{exp.title} at {exp.company}" for exp in profile.experiences[:3]]
                or [profile.summary[:200]],
            ),
            CoverSection(
                heading="Close",
                points=[
                    f"Fit score context: {fit.score}/100 on required skills already in my profile.",
                    "Happy to walk through the matched skills and gap plan in an interview.",
                ],
            ),
        ]
        return ApplicationPackage(
            tailored_bullets=bullets[:16],
            cover_outline=cover,
            keywords_to_mirror=keywords[:30],
        )
