"""Background career analyses with bounded concurrency and an in-memory store."""

from __future__ import annotations

import copy
import secrets
import threading
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from careerpilot.config import Settings
from careerpilot.engine import CareerPilot, ProgressHook
from careerpilot.llm import build_provider
from careerpilot.models import CareerBrief, JobPosting, Profile

JobState = Literal["queued", "running", "finished", "error"]
RunFn = Callable[[Profile, JobPosting, Settings, ProgressHook], CareerBrief]


def default_run(
    profile: Profile, job: JobPosting, settings: Settings, on_progress: ProgressHook
) -> CareerBrief:
    return CareerPilot(
        build_provider(settings), settings=settings, on_progress=on_progress
    ).analyze(profile, job)


def _now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return "an_" + secrets.token_hex(6)


class QueueFull(RuntimeError):
    """Too many analyses are queued or running."""


@dataclass
class AnalyzeRecord:
    """One analysis tracked by the service; events are append-only so polling is cheap."""

    id: str
    owner: str
    profile_id: str
    job_id: str
    profile_name: str
    job_title: str
    job_company: str
    provider: str
    created_at: datetime = field(default_factory=_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    state: JobState = "queued"
    brief: CareerBrief | None = None
    error: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    @property
    def done(self) -> bool:
        return self.state in ("finished", "error")

    def record_event(self, stage: str, data: dict[str, Any]) -> None:
        with self.lock:
            # Deep-copy so later mutations of the payload cannot rewrite history.
            self.events.append(
                {"seq": len(self.events), "stage": stage, "data": copy.deepcopy(data)}
            )

    def events_since(self, since: int) -> list[dict[str, Any]]:
        with self.lock:
            return copy.deepcopy(self.events[since:])

    def snapshot_brief(self) -> CareerBrief | None:
        with self.lock:
            return self.brief.model_copy(deep=True) if self.brief is not None else None


class AnalyzeManager:
    """Owns the worker pool and the analysis records.

    ``max_active`` bounds queued + running analyses (callers get :class:`QueueFull` -> 503);
    the oldest finished analyses are evicted beyond ``max_kept``. With ``inline=True`` the
    analysis runs inside :meth:`submit` (serverless mode).
    """

    def __init__(
        self,
        *,
        max_workers: int = 2,
        max_active: int = 8,
        max_kept: int = 200,
        run_fn: RunFn = default_run,
        inline: bool = False,
    ) -> None:
        self.inline = inline
        self._executor = (
            None
            if inline
            else ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="analyze")
        )
        self._max_active = max_active
        self._max_kept = max_kept
        self._run_fn = run_fn
        self._records: OrderedDict[str, AnalyzeRecord] = OrderedDict()
        self._lock = threading.Lock()

    def submit(
        self,
        *,
        owner: str,
        profile: Profile,
        job: JobPosting,
        profile_id: str,
        job_id: str,
        settings: Settings,
    ) -> AnalyzeRecord:
        record = AnalyzeRecord(
            id=new_id(),
            owner=owner,
            profile_id=profile_id,
            job_id=job_id,
            profile_name=profile.name,
            job_title=job.title,
            job_company=job.company,
            provider=settings.provider,
        )
        with self._lock:
            if sum(1 for r in self._records.values() if not r.done) >= self._max_active:
                raise QueueFull("Too many analyses in progress; try again shortly")
            self._records[record.id] = record
            self._evict_unlocked()
        if self._executor is None:
            self._execute(record, profile, job, settings)
        else:
            self._executor.submit(self._execute, record, profile, job, settings)
        return record

    def get(self, analyze_id: str, owner: str | None) -> AnalyzeRecord | None:
        """Look up an analysis; ``owner=None`` means the caller may see every analysis."""
        with self._lock:
            record = self._records.get(analyze_id)
        if record is None or (owner is not None and record.owner != owner):
            return None
        return record

    def list(self, owner: str | None, limit: int = 50) -> list[AnalyzeRecord]:
        with self._lock:
            records = [
                r for r in reversed(self._records.values()) if owner is None or r.owner == owner
            ]
        return records[:limit]

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for r in self._records.values() if not r.done)

    def shutdown(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)

    def _evict_unlocked(self) -> None:
        overflow = len(self._records) - self._max_kept
        if overflow <= 0:
            return
        for rid in [rid for rid, r in self._records.items() if r.done][:overflow]:
            del self._records[rid]

    def _execute(
        self, record: AnalyzeRecord, profile: Profile, job: JobPosting, settings: Settings
    ) -> None:
        with record.lock:
            record.state = "running"
            record.started_at = _now()
        try:
            brief = self._run_fn(profile, job, settings, record.record_event)
        except Exception as exc:  # a crashed analysis must never take down the worker
            with record.lock:
                record.state = "error"
                record.error = f"{type(exc).__name__}: {exc}"[:500]
                record.finished_at = _now()
            return
        with record.lock:
            record.brief = brief
            record.state = "finished"
            record.finished_at = _now()
