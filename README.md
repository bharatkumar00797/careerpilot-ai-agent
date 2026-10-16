# CareerPilot

**Personal AI career agent** — turns a structured career profile and a job
description into a fit score with evidence, a skill-gap plan, an interview prep
pack, and a tailored application package.

> Core engine + CLI + offline mock provider + FastAPI dashboard and multi-platform
> deploy configs. Status badges and the deep README arrive with the 1.0.0 release.

## Quick start (offline)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
careerpilot profiles
careerpilot jobs
careerpilot analyze ml-engineer ml-platform
```

The default provider is a deterministic offline mock — no API keys required.

## HTTP API + dashboard

```bash
careerpilot serve --dev
# open http://127.0.0.1:8000
```

- `POST /api/analyze` — sync (200) or async (202) career brief
- `GET /api/analyze/{id}` / `.../events` / `.../brief.md`
- `GET /api/profiles`, `GET /api/jobs`, `GET /api/config`, `/healthz`, `/docs`
- Access modes: API-key / dev / public-demo (packaged demos + mock only)

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

## Deploy

Docker / Compose / Render / Fly / Railway / Vercel configs ship in the repo root.
See `.env.example` for every `CAREERPILOT_*` service variable.

## License

MIT — see [LICENSE](LICENSE).
