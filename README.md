# CareerPilot

**Personal AI career agent** — turns a structured career profile and a job
description into a fit score with evidence, a skill-gap plan, an interview prep
pack, and a tailored application package.

> Session 1 ships the core engine, CLI, offline mock provider, and packaged
> demos. FastAPI dashboard, deploy configs, and the full docs land in later
> sessions. Status badges and the deep README arrive with the 1.0.0 release.

## Quick start (offline)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
careerpilot profiles
careerpilot jobs
careerpilot analyze ml-engineer ml-platform
```

The default provider is a deterministic offline mock — no API keys required.

## What it produces

| Output | Contents |
|--------|----------|
| Fit report | 0–100 score, matched / missing skills, evidence bullets, summary |
| Skill gaps | Prioritised missing skills with practice plans |
| Interview pack | Behavioural + technical questions and talking points |
| Application package | Tailored bullets, cover outline, keywords to mirror |

## Design principles

- **Rules first.** Deterministic skill/title/experience scoring runs before any
  model call and is the score floor.
- **No invented facts.** The model may only narrate and rank within skills
  already present in the profile or job description.
- **Untrusted wrappers.** Profile and JD text are wrapped in
  `<untrusted-profile>` / `<untrusted-job>` with delimiter look-alikes defanged.
- **Pluggable LLM.** `mock` (default) | `openai` | `groq` | `ollama` via
  `CAREERPILOT_*` env vars.

## License

MIT — see [LICENSE](LICENSE).
