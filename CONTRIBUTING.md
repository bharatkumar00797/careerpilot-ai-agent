# Contributing to CareerPilot

Thanks for your interest in improving this personal AI career agent. Bug reports,
new practice plans, packaged profiles/jobs, documentation fixes and pull requests
are all welcome.

## Development setup

Requirements: Python 3.11 to 3.13, `git`. Docker is optional (only for the
container checks).

```bash
git clone https://github.com/bharatkumar00797/careerpilot-ai-agent.git
cd careerpilot-ai-agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Everything runs offline with the default `mock` provider, so no API key is needed
for development or tests. To try a real model, copy `.env.example` to `.env` and
set `CAREERPILOT_PROVIDER` / `CAREERPILOT_BASE_URL` / `CAREERPILOT_API_KEY` /
`CAREERPILOT_MODEL`. Never commit `.env` or any key.

## Checks

Run these before opening a pull request; CI runs the same commands on Python
3.11, 3.12 and 3.13.

```bash
ruff check .            # lint
ruff format .           # format (CI uses: ruff format --check .)
mypy                    # strict type checking of src/careerpilot
pytest                  # full test suite, offline
```

Optional end-to-end checks:

```bash
careerpilot analyze ml-engineer ml-platform
careerpilot analyze ml-engineer product-engineer
careerpilot serve --dev                               # dashboard on http://127.0.0.1:8000
python scripts/smoke_test.py http://127.0.0.1:8000
docker compose up --build --wait                      # hardened container
```

## Guidelines

- Keep the mock provider the default: every feature must work without network
  access or keys.
- New code is fully typed (`mypy --strict` must pass) and comes with tests.
- The model never invents employer names, titles, or unverifiable metrics. Fit
  scoring stays deterministic; the LLM only narrates and ranks within skills
  already present in the profile or job.
- Profile and JD text fed to the model must stay wrapped in
  `<untrusted-profile>` / `<untrusted-job>` with delimiter look-alikes defanged.
- Injection-pattern hits become `security_flags` on the brief; they are treated
  as data, never as instructions.
- Anything touching auth, access modes, rate limiting or the body cap needs a
  test proving the control holds (see `tests/test_api.py`).
- Adding a profile or job: ship JSON under `src/careerpilot/data/` and cover it
  in engine / smoke tests.

## Commit style

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(gaps): add practice plan for GraphQL
fix(match): weight must-have skills above nice-to-haves
docs: document public-demo ownership
test: cover injection flag on crafted JD
ci: smoke-test the Docker image
```

Keep commits small and focused, write the subject in the imperative mood, and
update `CHANGELOG.md` under **Unreleased** for user-visible changes.

## Reporting security issues

Please do not open public issues for vulnerabilities; see [SECURITY.md](SECURITY.md).
