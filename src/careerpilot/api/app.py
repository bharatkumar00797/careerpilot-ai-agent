"""FastAPI application: REST endpoints for career analysis plus the static dashboard."""

from __future__ import annotations

import hashlib
import math
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi import Path as PathParam
from fastapi import status as http
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from careerpilot import __version__
from careerpilot.api.jobs import AnalyzeManager, AnalyzeRecord, QueueFull, RunFn, default_run
from careerpilot.api.middleware import BodyLimitMiddleware, SecurityHeadersMiddleware
from careerpilot.api.schemas import (
    AnalyzeCreate,
    AnalyzeCreatedOut,
    AnalyzeDetailOut,
    AnalyzeListOut,
    AnalyzeSummaryOut,
    ConfigOut,
    EventOut,
    EventsOut,
    HealthOut,
    JobListOut,
    JobSummaryOut,
    ProfileListOut,
    ProfileSummaryOut,
)
from careerpilot.api.security import ApiKeyAuth, RateLimiter
from careerpilot.api.settings import ApiSettings
from careerpilot.config import Settings
from careerpilot.engine import brief_to_markdown
from careerpilot.ingest import list_jobs, list_profiles, load_job, load_profile
from careerpilot.models import JobPosting, Profile

STATIC_DIR = Path(__file__).parent / "static"
MAX_BODY_BYTES = 64 * 1024
IdParam = Annotated[str, PathParam(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]


@dataclass(frozen=True)
class Caller:
    """``owner`` tags new analyses, ``scope`` limits visibility (``None`` = all),
    ``client`` keys rate limits and ``trusted`` unlocks custom inputs and real providers."""

    owner: str
    scope: str | None
    client: str
    trusted: bool


def client_ip(request: Request, trust_proxy: bool) -> str:
    if trust_proxy:
        # The right-most hop is the one appended by the trusted edge proxy; anything to its
        # left is client-supplied and can be forged.
        hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",")]
        hops = [h for h in hops if h]
        if hops:
            return hops[-1][:64]
    return request.client.host if request.client else "unknown"


def presented_key(request: Request) -> str | None:
    key = request.headers.get("x-api-key")
    if key and key.strip():
        return key.strip()
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()
    return None


def _retry_after(seconds: float) -> dict[str, str]:
    return {"Retry-After": str(max(1, math.ceil(seconds)))}


@dataclass(frozen=True)
class AccessGuard:
    """Authenticates a request and applies the general per-caller rate limit."""

    settings: ApiSettings
    auth: ApiKeyAuth
    limiter: RateLimiter

    def identify(self, request: Request) -> Caller | None:
        if self.auth.enabled:
            fp = self.auth.verify(presented_key(request))
            return Caller(f"key:{fp}", f"key:{fp}", f"key:{fp}", True) if fp else None
        ip = client_ip(request, self.settings.trust_proxy)
        if self.settings.dev_mode:
            return Caller("dev", None, f"ip:{ip}", True)
        anon = "anon:" + hashlib.sha256(ip.encode()).hexdigest()[:12]
        return Caller(anon, anon, f"ip:{ip}", False)

    def __call__(self, request: Request) -> Caller:
        who = self.identify(request)
        if who is None:
            raise HTTPException(
                http.HTTP_401_UNAUTHORIZED,
                "Missing or invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        retry = self.limiter.check(who.client)
        if retry is not None:
            raise HTTPException(
                http.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded", headers=_retry_after(retry)
            )
        return who


def get_caller(request: Request) -> Caller:
    guard: AccessGuard = request.app.state.guard
    return guard(request)


CallerDep = Annotated[Caller, Depends(get_caller)]


def _summary(record: AnalyzeRecord) -> AnalyzeSummaryOut:
    with record.lock:
        brief, state, finished = record.brief, record.state, record.finished_at
    return AnalyzeSummaryOut(
        id=record.id,
        state=state,
        profile_id=record.profile_id,
        job_id=record.job_id,
        profile_name=record.profile_name,
        job_title=record.job_title,
        job_company=record.job_company,
        provider=record.provider,
        score=brief.fit.score if brief else None,
        created_at=record.created_at,
        finished_at=finished,
    )


def _detail(record: AnalyzeRecord, *, simulated: bool) -> AnalyzeDetailOut:
    with record.lock:
        error, started, count = record.error, record.started_at, len(record.events)
    brief = record.snapshot_brief()
    return AnalyzeDetailOut(
        **_summary(record).model_dump(),
        started_at=started,
        error=error,
        event_count=count,
        brief=brief,
        simulated=simulated,
    )


def create_app(
    settings: ApiSettings | None = None,
    base_settings: Settings | None = None,
    *,
    run_fn: RunFn = default_run,
) -> FastAPI:
    cfg = settings or ApiSettings.from_env()
    base = base_settings or Settings.from_env()
    auth = ApiKeyAuth(cfg.api_keys)
    analyze_limiter = RateLimiter(cfg.analyze_limit_per_minute)
    manager = AnalyzeManager(
        max_workers=cfg.max_concurrent_runs,
        max_active=cfg.max_queued_runs,
        max_kept=cfg.max_analyses_kept,
        run_fn=run_fn,
        inline=cfg.sync_runs,
    )
    profile_ids = list_profiles()
    job_ids = list_jobs()
    simulated = cfg.public_demo

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        manager.shutdown()

    app = FastAPI(
        title="CareerPilot AI API",
        version=__version__,
        description=(
            "Personal AI career agent: fit scoring, skill-gap plans, interview prep, "
            "and tailored application packages from a structured profile and job description."
        ),
        lifespan=lifespan,
    )
    app.state.guard = AccessGuard(cfg, auth, RateLimiter(cfg.rate_limit_per_minute))
    app.state.manager = manager

    if cfg.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cfg.cors_origins),
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-API-Key", "Authorization"],
            allow_credentials=False,
            max_age=600,
        )
    app.add_middleware(BodyLimitMiddleware, max_bytes=MAX_BODY_BYTES)
    app.add_middleware(SecurityHeadersMiddleware)

    def load(analyze_id: str, who: Caller) -> AnalyzeRecord:
        record = manager.get(analyze_id, who.scope)
        if record is None:
            raise HTTPException(http.HTTP_404_NOT_FOUND, "Analysis not found")
        return record

    def resolve_inputs(body: AnalyzeCreate, who: Caller) -> tuple[Profile, JobPosting, str, str]:
        if body.profile_id is not None and body.job_id is not None:
            try:
                profile = load_profile(body.profile_id)
            except (KeyError, FileNotFoundError, ValueError) as exc:
                raise HTTPException(
                    http.HTTP_422_UNPROCESSABLE_CONTENT, f"unknown profile {body.profile_id!r}"
                ) from exc
            try:
                job = load_job(body.job_id)
            except (KeyError, FileNotFoundError, ValueError) as exc:
                raise HTTPException(
                    http.HTTP_422_UNPROCESSABLE_CONTENT, f"unknown job {body.job_id!r}"
                ) from exc
            return profile, job, body.profile_id, body.job_id
        if not who.trusted:
            raise HTTPException(
                http.HTTP_403_FORBIDDEN,
                "Public demo: only packaged profiles and jobs are enabled "
                "(custom ones need an API key)",
            )
        assert body.profile is not None and body.job is not None
        return body.profile, body.job, "custom", "custom"

    # ------------------------------------------------------------------ meta
    @app.get("/healthz", response_model=HealthOut, tags=["meta"])
    def healthz() -> HealthOut:
        return HealthOut(version=__version__, active_analyses=manager.active_count())

    @app.get("/api/config", response_model=ConfigOut, tags=["meta"])
    def config(request: Request) -> ConfigOut:
        guard: AccessGuard = request.app.state.guard
        who = guard.identify(request)
        return ConfigOut(
            version=__version__,
            auth_required=cfg.auth_enabled,
            access_mode=cfg.access_mode,
            authenticated=who is not None and cfg.auth_enabled,
            custom_inputs_allowed=not cfg.public_demo,
            providers=["mock"] if cfg.public_demo else sorted({"mock", base.provider}),
            default_provider="mock" if cfg.public_demo else base.provider,
            sync_runs=cfg.sync_runs,
            profiles=profile_ids,
            jobs=job_ids,
            simulated=simulated,
        )

    @app.get("/api/profiles", response_model=ProfileListOut, tags=["meta"])
    def profiles(_: CallerDep) -> ProfileListOut:
        out: list[ProfileSummaryOut] = []
        for pid in profile_ids:
            p = load_profile(pid)
            out.append(
                ProfileSummaryOut(
                    id=pid, name=p.name, headline=p.headline, target_roles=list(p.target_roles)
                )
            )
        return ProfileListOut(profiles=out)

    @app.get("/api/profiles/{profile_id}", response_model=Profile, tags=["meta"])
    def profile_detail(profile_id: IdParam, _: CallerDep) -> Profile:
        try:
            return load_profile(profile_id)
        except (KeyError, FileNotFoundError, ValueError) as exc:
            raise HTTPException(http.HTTP_404_NOT_FOUND, "Profile not found") from exc

    @app.get("/api/jobs", response_model=JobListOut, tags=["meta"])
    def jobs(_: CallerDep) -> JobListOut:
        out: list[JobSummaryOut] = []
        for jid in job_ids:
            j = load_job(jid)
            out.append(JobSummaryOut(id=jid, title=j.title, company=j.company, location=j.location))
        return JobListOut(jobs=out)

    @app.get("/api/jobs/{job_id}", response_model=JobPosting, tags=["meta"])
    def job_detail(job_id: IdParam, _: CallerDep) -> JobPosting:
        try:
            return load_job(job_id)
        except (KeyError, FileNotFoundError, ValueError) as exc:
            raise HTTPException(http.HTTP_404_NOT_FOUND, "Job not found") from exc

    # ------------------------------------------------------------- analyze
    @app.post(
        "/api/analyze",
        response_model=AnalyzeCreatedOut,
        status_code=http.HTTP_202_ACCEPTED,
        tags=["analyze"],
        responses={200: {"description": "Finished brief (sync mode)"}},
    )
    def create_analyze(
        body: AnalyzeCreate, who: CallerDep, response: Response
    ) -> AnalyzeCreatedOut:
        use_configured = body.provider == "configured" or (
            body.provider is None and not cfg.public_demo
        )
        provider = base.provider if use_configured else "mock"
        if (provider != "mock" or body.provider == "configured") and not who.trusted:
            raise HTTPException(
                http.HTTP_403_FORBIDDEN, "Only the offline mock provider is enabled here"
            )
        profile, job, profile_id, job_id = resolve_inputs(body, who)
        # Only well-formed requests count towards the stricter analyze-creation limit.
        retry = analyze_limiter.check(who.client)
        if retry is not None:
            raise HTTPException(
                http.HTTP_429_TOO_MANY_REQUESTS,
                "Analyze creation limit exceeded",
                headers=_retry_after(retry),
            )
        try:
            record = manager.submit(
                owner=who.owner,
                profile=profile,
                job=job,
                profile_id=profile_id,
                job_id=job_id,
                settings=replace(base, provider=provider),
            )
        except QueueFull as exc:
            raise HTTPException(
                http.HTTP_503_SERVICE_UNAVAILABLE, str(exc), headers={"Retry-After": "10"}
            ) from exc
        detail = _detail(record, simulated=simulated).model_dump()
        if not manager.inline:
            return AnalyzeCreatedOut(**detail)  # 202: poll the events endpoint
        response.status_code = http.HTTP_200_OK
        events = [EventOut(**e) for e in record.events_since(0)]
        return AnalyzeCreatedOut(**detail, events=events)

    @app.get("/api/analyze", response_model=AnalyzeListOut, tags=["analyze"])
    def list_analyze(
        who: CallerDep, limit: Annotated[int, Query(ge=1, le=100)] = 25
    ) -> AnalyzeListOut:
        return AnalyzeListOut(analyses=[_summary(r) for r in manager.list(who.scope, limit)])

    @app.get("/api/analyze/{analyze_id}", response_model=AnalyzeDetailOut, tags=["analyze"])
    def get_analyze(analyze_id: IdParam, who: CallerDep) -> AnalyzeDetailOut:
        return _detail(load(analyze_id, who), simulated=simulated)

    @app.get("/api/analyze/{analyze_id}/events", response_model=EventsOut, tags=["analyze"])
    def get_events(
        analyze_id: IdParam,
        who: CallerDep,
        since: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    ) -> EventsOut:
        record = load(analyze_id, who)
        with record.lock:
            state, done = record.state, record.done
            events = record.events_since(since)
        return EventsOut(
            id=record.id,
            state=state,
            done=done,
            next_cursor=since + len(events),
            events=[EventOut(**e) for e in events],
        )

    @app.get(
        "/api/analyze/{analyze_id}/brief.md",
        response_class=PlainTextResponse,
        tags=["analyze"],
        responses={200: {"content": {"text/markdown": {}}}},
    )
    def get_brief_markdown(analyze_id: IdParam, who: CallerDep) -> PlainTextResponse:
        record = load(analyze_id, who)
        brief = record.snapshot_brief()
        if brief is None:
            raise HTTPException(http.HTTP_409_CONFLICT, "Analysis has not finished yet")
        return PlainTextResponse(
            brief_to_markdown(brief), media_type="text/markdown; charset=utf-8"
        )

    # ------------------------------------------------------------- dashboard
    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
