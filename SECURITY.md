# Security Policy

CareerPilot is an AI career agent that scores profiles against job descriptions
and produces interview and application drafts, so bypasses of its safety controls
are treated as vulnerabilities. The design is described in the
[security model](README.md#security-model) section of the README.

## Supported versions

| Version | Supported |
| --- | --- |
| 1.0.x | yes |
| < 1.0 | no |

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

- Use GitHub's private vulnerability reporting:
  **Security → Report a vulnerability** on
  <https://github.com/bharatkumar00797/careerpilot-ai-agent/security>.
- Include the affected version or commit, a description of the impact, and steps
  or a proof of concept to reproduce it.

You can expect an acknowledgement within 3 working days and a status update
within 10 working days. Once a fix is released we are happy to credit you in the
changelog unless you prefer to stay anonymous.

## Scope

In scope:

- The model inventing employer names, titles, dates, or unverifiable metrics that
  reach the returned `CareerBrief` or Markdown brief.
- Prompt / profile / JD injection that causes the agent to follow attacker
  instructions (beyond recording a `security_flag` and continuing with wrapped
  data).
- Escaping the untrusted wrappers so content is treated as system instructions.
- Authentication or authorization bypass in the REST API, a real provider in
  public-demo mode, or seeing another caller's analyses.
- Bypassing rate limits or the request body cap; XSS or CSP bypass in the
  dashboard.
- Secrets exposed in API responses, logs or the published Docker image.

Out of scope:

- A suboptimal fit ranking when the score floor is still produced by deterministic
  rules (model narration is advisory; the rule score is the floor).
- Shared public-demo identity when `CAREERPILOT_TRUST_PROXY` is unset behind a
  reverse proxy.
- In-memory state loss across restarts or serverless instances (documented
  caveat).
- Advice quality of practice plans or interview questions when they stay within
  profile / JD facts.
- Vulnerabilities in third-party platforms or dependencies without a demonstrated
  impact on CareerPilot.
