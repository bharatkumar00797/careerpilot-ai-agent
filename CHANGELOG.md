# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.0] - 2026-10-16

First stable release.

### Added

- Rules-first career analysis pipeline: ingest → sanitize / injection scan /
  untrusted wrappers → deterministic fit score → skill-gap plans → LLM enrich →
  assembled `CareerBrief` (fit, gaps, interview pack, application package, flags).
- Deterministic fit scoring from skill overlap (weighted by level), must-have
  coverage, title / target-role overlap and an experience-years heuristic; the
  score floor never depends on the model.
- Curated practice plans for missing required skills (Python, SQL, system design,
  Kubernetes, leadership, ML stack, and a generic fallback).
- Interview prep pack with behavioural and technical questions plus talking points
  anchored in real profile employers and titles — never invented companies or
  unverifiable metrics.
- Application package: tailored bullets drawn from profile experience text, cover
  outline sections, and keywords to mirror that already exist in the profile or
  matched skill set.
- Pluggable LLM providers: offline deterministic `mock` (default), plus
  OpenAI-compatible `openai` / Groq / Ollama for narration that only restates
  allowlisted skills.
- Prompt-injection scan with `security_flags` on the brief; profile and JD text
  wrapped in `<untrusted-profile>` / `<untrusted-job>` with delimiter look-alikes
  defanged.
- Packaged demos: profiles `ml-engineer`, `fullstack-pm-hybrid`; jobs
  `ml-platform`, `senior-backend`, `product-engineer`.
- CLI: `careerpilot profiles | jobs | match | prep | package | analyze | serve`.
- FastAPI service with analyze / events / brief.md endpoints, OpenAPI docs,
  api-key / dev / public-demo access modes, sliding-window rate limits, 64 KB body
  cap, strict CSP and security headers.
- No-build dashboard: overview (fit + skills), gaps, interview, application,
  Markdown brief, history, `#analyze=&tab=` deep links.
- Hardened multi-stage Docker image, docker compose, Render, Fly.io, Railway and
  Vercel configs, end-to-end smoke test script and Docker smoke job in CI.

[Unreleased]: https://github.com/bharatkumar00797/careerpilot-ai-agent/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/bharatkumar00797/careerpilot-ai-agent/releases/tag/v1.0.0
