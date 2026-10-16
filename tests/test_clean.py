"""Repository cleanliness: no watermarks, no embedded secrets."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Generic attribution trailers that must never appear in the tree. Assembled so
# this file does not contain the phrases as contiguous literals.
_BAN_SNIPPETS = tuple(
    "".join(parts)
    for parts in (
        ("Gener", "ated by"),
        ("Co-authored", "-by"),
        ("Signed-off-by: ", "bot"),
        ("[", "bot]"),
    )
)

_SECRET_PATTERNS = (
    "sk-proj-",
    "sk-ant-",
    "ghp_",
    "BEGIN RSA PRIVATE KEY",
)

_SKIP_PARTS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
}


def _iter_text_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_PARTS for part in path.parts):
            continue
        if path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pyc", ".so"}:
            continue
        files.append(path)
    return files


def test_no_watermark_snippets() -> None:
    offenders: list[str] = []
    for path in _iter_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for ban in _BAN_SNIPPETS:
            if ban in text:
                offenders.append(f"{path.relative_to(ROOT)}: {ban}")
    assert not offenders, "watermark / attribution snippets found:\n" + "\n".join(offenders)


def test_no_embedded_secret_markers() -> None:
    offenders: list[str] = []
    for path in _iter_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if path.name in {"test_clean.py", ".env.example"}:
            continue
        for pat in _SECRET_PATTERNS:
            if pat in text:
                offenders.append(f"{path.relative_to(ROOT)}: {pat}")
    assert not offenders, "secret-like markers found:\n" + "\n".join(offenders)
