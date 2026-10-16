"""CareerPilot command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from careerpilot import __version__
from careerpilot.config import Settings
from careerpilot.engine import CareerPilot, brief_to_markdown
from careerpilot.ingest import list_jobs, list_profiles, load_job, load_profile
from careerpilot.llm import build_provider


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="careerpilot",
        description="Personal AI career agent — fit, gaps, interview prep, application package.",
    )
    parser.add_argument("--version", action="version", version=f"careerpilot {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("profiles", help="List packaged demo profiles")
    sub.add_parser("jobs", help="List packaged demo job postings")

    match_p = sub.add_parser("match", help="Rule-based fit score only")
    _add_pair_args(match_p)
    match_p.add_argument("--json", action="store_true", help="Emit JSON")

    prep_p = sub.add_parser("prep", help="Interview prep pack")
    _add_pair_args(prep_p)
    prep_p.add_argument("--json", action="store_true")

    pkg_p = sub.add_parser("package", help="Tailored application package")
    _add_pair_args(pkg_p)
    pkg_p.add_argument("--json", action="store_true")

    analyze_p = sub.add_parser("analyze", help="Full career brief (fit + gaps + prep + package)")
    _add_pair_args(analyze_p)
    analyze_p.add_argument("--json", action="store_true")
    analyze_p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write brief.md and brief.json into this directory",
    )

    args = parser.parse_args(argv)
    if args.command == "profiles":
        for name in list_profiles():
            print(name)
        return 0
    if args.command == "jobs":
        for name in list_jobs():
            print(name)
        return 0

    settings = Settings.from_env()
    if getattr(args, "provider", None):
        settings = Settings(
            provider=args.provider,
            base_url=settings.base_url,
            api_key=settings.api_key,
            model=settings.model,
            timeout=settings.timeout,
        )
    provider = build_provider(settings)
    engine = CareerPilot(provider=provider, settings=settings)

    profile = load_profile(args.profile)
    job = load_job(args.job)
    brief = engine.analyze(profile, job)

    if args.command == "match":
        payload: Any = brief.fit.model_dump()
        return _emit(payload, as_json=args.json, title="Fit report")
    if args.command == "prep":
        return _emit(brief.interview.model_dump(), as_json=args.json, title="Interview pack")
    if args.command == "package":
        return _emit(brief.application.model_dump(), as_json=args.json, title="Application package")
    if args.command == "analyze":
        if args.out is not None:
            args.out.mkdir(parents=True, exist_ok=True)
            (args.out / "brief.json").write_text(
                json.dumps(brief.model_dump(), indent=2) + "\n", encoding="utf-8"
            )
            (args.out / "brief.md").write_text(brief_to_markdown(brief), encoding="utf-8")
            print(f"Wrote {args.out / 'brief.md'} and {args.out / 'brief.json'}")
            return 0
        if args.json:
            print(json.dumps(brief.model_dump(), indent=2))
            return 0
        print(brief_to_markdown(brief))
        return 0
    parser.error(f"unknown command {args.command}")
    return 2


def _add_pair_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("profile", help="Packaged profile id or path to JSON")
    parser.add_argument("job", help="Packaged job id or path to JSON")
    parser.add_argument(
        "--provider",
        choices=["mock", "openai", "groq", "ollama"],
        default=None,
        help="Override CAREERPILOT_PROVIDER for this run",
    )


def _emit(payload: dict[str, Any], *, as_json: bool, title: str) -> int:
    if as_json:
        print(json.dumps(payload, indent=2))
        return 0
    print(f"# {title}")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
