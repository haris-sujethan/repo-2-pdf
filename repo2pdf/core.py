# repo2pdf/core.py
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Any

from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern

from repo2pdf.pdf import generate_pdf, PDFMeta  # updated renderer

# Directories we always skip anywhere in the path
EXCLUDE_DIRS = {
    ".git", ".github", "node_modules", "dist", "build", "out", "target",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".venv", "venv",
    ".tox", ".idea", ".vscode"
}

# Files we always skip by name
ALWAYS_SKIP_FILENAMES = {"repo_output.pdf", "repo2pdf.pdf"}

# Obvious binary extensions (expanded)
BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".pdf", ".zip", ".gz", ".7z", ".tar", ".rar",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".bmp", ".tiff", ".psd", ".svg",
    ".mp3", ".mp4", ".mov", ".avi", ".mkv",
    ".exe", ".dll", ".so", ".dylib",
    ".bin", ".class", ".o", ".a",
    ".lock",
}

# Max size we’ll read as “text”
MAX_TEXT_BYTES = 1_000_000  # 1 MB


def _gitignore(root: Path) -> PathSpec:
    gi = root / ".gitignore"
    lines = gi.read_text().splitlines() if gi.exists() else []
    return PathSpec.from_lines(GitWildMatchPattern, lines)


def _skip_dir(p: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in p.parts)


def _looks_binary(head: bytes) -> bool:
    if b"\x00" in head:
        return True
    if head.startswith(b"%PDF-"):
        return True
    if head.startswith(b"\x1f\x8b"):       # gzip
        return True
    if head.startswith(b"PK\x03\x04"):     # zip/jar/docx/etc.
        return True
    printable = sum(32 <= b <= 126 or b in (9, 10, 13) for b in head)
    return (len(head) - printable) / max(1, len(head)) > 0.20


def _collect_files(root: Path, exclude_exts: set[str]) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
    spec = _gitignore(root)
    files: List[Tuple[str, str]] = []
    counts = {
        "gitignored": 0,
        "manual_exclude": 0,
        "excluded_dir": 0,
        "binary_ext": 0,
        "binary_magic": 0,
        "too_large": 0,
        "read_errors": 0,
    }

    for p in root.rglob("*"):
        if p.is_dir():
            if _skip_dir(p):
                # skip entire subtree
                counts["excluded_dir"] += 1
                continue
            continue

        rel = p.relative_to(root).as_posix()

        # .gitignore + manual skips
        if rel.startswith(".git/") or spec.match_file(rel):
            counts["gitignored"] += 1
            continue
        if p.name in ALWAYS_SKIP_FILENAMES:
            counts["manual_exclude"] += 1
            continue
        if _skip_dir(p):
            counts["excluded_dir"] += 1
            continue

        ext = p.suffix.lower()
        if ext in exclude_exts or ext in BINARY_EXTS:
            counts["binary_ext"] += 1
            continue

        try:
            if p.stat().st_size > MAX_TEXT_BYTES:
                counts["too_large"] += 1
                continue
        except Exception:
            pass

        try:
            with p.open("rb") as f:
                head = f.read(4096)
                if _looks_binary(head):
                    counts["binary_magic"] += 1
                    continue
                data = head + f.read()
            text = data.decode("utf-8", errors="replace")
        except Exception:
            counts["read_errors"] += 1
            continue

        files.append((rel, text))

    files.sort(key=lambda t: t[0])
    summary = {"counts": counts, "notes": [], "packed_small_files": 0}
    return files, summary


def _resolve_output_path(output_path: str | None, root: Path) -> Path:
    """
    If output_path is:
      - empty/None -> use CWD/repo2pdf-<root>-YYYYmmdd-HHMM.pdf
      - a directory -> append repo2pdf-<root>-YYYYmmdd-HHMM.pdf
      - a file path without .pdf -> add .pdf
      - a file path with .pdf -> use as-is
    """
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    default_name = f"repo2pdf-{root.name}-{ts}.pdf"

    if not output_path or output_path.strip() == "":
        return Path(os.getcwd()) / default_name

    p = Path(output_path).expanduser()
    if p.is_dir() or str(output_path).endswith(os.sep):
        return p / default_name

    if p.suffix.lower() != ".pdf":
        p = p.with_suffix(".pdf")
    return p


def _build_json_summary(root: Path, files: List[Tuple[str, str]]) -> dict:
    from datetime import datetime, timezone
    entries = []
    for rel, content in files:
        p = root / rel
        try:
            size = p.stat().st_size
        except Exception:
            size = len(content.encode("utf-8", errors="ignore"))
        lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        entries.append({
            "path": rel,
            "ext": Path(rel).suffix.lower(),
            "size_bytes": size,
            "line_count": lines,
        })
    return {
        "repo_name": root.name,
        "root": str(root),
        "file_count": len(entries),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": entries,
    }


def _render(root: Path, output_path: str | None, exclude_list: list[str] | None, repo_url: str | None, want_json: bool):
    # Normalize CLI excludes (like ".png,.jpg") into a set of extensions
    exclude_exts = set()
    for item in (exclude_list or []):
        for token in item.split(","):
            token = token.strip()
            if token and token.startswith("."):
                exclude_exts.add(token.lower())

    files, summary = _collect_files(root, exclude_exts)

    meta = PDFMeta(
        title=f"repo2pdf — {root.name}",
        subtitle=str(root),
        repo_url=repo_url,
    )

    out_path = _resolve_output_path(output_path, root)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate PDF (summary appended in appendix)
    generate_pdf(files, str(out_path), meta, summary=summary)

    if want_json:
        out_json = _build_json_summary(root, files)
        json_path = out_path.with_suffix(".json")
        json_path.write_text(json.dumps(out_json, indent=2), encoding="utf-8")

    print(f"\nPDF saved to: {out_path}")
    if want_json:
        print(f"JSON saved to: {out_path.with_suffix('.json')}")


# Public entry points expected by cli.py

def process_local_repo(path: str, want_json: bool, output_path: str | None, exclude_list: list[str]):
    root = Path(path or ".").resolve()
    _render(root, output_path, exclude_list, repo_url=None, want_json=want_json)


def process_remote_repo(url: str, want_json: bool, output_path: str | None, exclude_list: list[str]):
    from git import Repo  # requires GitPython
    with tempfile.TemporaryDirectory(prefix="repo2pdf_") as tmp:
        tmp_path = Path(tmp)
        Repo.clone_from(url, tmp_path)
        _render(tmp_path, output_path, exclude_list, repo_url=url, want_json=want_json)
