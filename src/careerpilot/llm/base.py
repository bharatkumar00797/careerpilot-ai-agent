"""Provider-agnostic chat completion interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal, Protocol

from careerpilot.models import (
    ApplicationPackage,
    FitReport,
    InterviewPack,
    JobPosting,
    Profile,
    SkillGap,
)

Role = Literal["system", "user", "assistant"]


class LLMError(RuntimeError):
    """Raised when a provider cannot produce a completion."""


@dataclass(frozen=True)
class Message:
    role: Role
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class Completion:
    content: str
    model: str
    usage: Usage = field(default_factory=Usage)


class LLMProvider(ABC):
    """Minimal chat-completion contract."""

    name: str = "base"

    @abstractmethod
    def complete(self, messages: list[Message], *, temperature: float = 0.0) -> Completion:
        """Return the assistant reply for the given conversation."""


class CareerEnricher(Protocol):
    """Optional enrichment surface used by the engine (mock implements this directly)."""

    name: str

    def enrich(
        self,
        profile: Profile,
        job: JobPosting,
        fit: FitReport,
        gaps: list[SkillGap],
    ) -> tuple[FitReport, list[SkillGap], InterviewPack, ApplicationPackage]: ...
