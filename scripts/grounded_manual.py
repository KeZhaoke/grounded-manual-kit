#!/usr/bin/env python3
"""Grounded manual evidence-pack toolkit.

This script is intentionally stdlib-first. PDF extraction uses optional pypdf;
all other commands should run in a clean Python installation.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import textwrap
import unicodedata
from pathlib import Path
from typing import Iterable


SCHEMA_VERSION = "0.1.0"
TOOL_NAME = "grounded-manual-kit"
TOOL_VERSION = "0.1.0"
DEFAULT_ROOT = Path("docs") / "grounded_manual"
TEXT_SUFFIXES = {
    ".md",
    ".markdown",
    ".txt",
    ".rst",
    ".py",
    ".m",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".cs",
    ".go",
    ".rs",
    ".sh",
    ".bat",
    ".ps1",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".tex",
}


def utc_now() -> str:
    return _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, text: str, force: bool = False) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{lineno}: invalid JSONL: {exc}") from exc
    return rows


def dump_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def relpath(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def package_root(start: Path | None = None) -> Path:
    start = (start or Path.cwd()).resolve()
    candidates = [start, *start.parents]
    for cand in candidates:
        if (cand / "docs" / "grounded_manual" / "project.yaml").exists():
            return cand / "docs" / "grounded_manual"
        if (cand / "project.yaml").exists() and cand.name == "grounded_manual":
            return cand
    default = start / DEFAULT_ROOT
    if default.exists():
        return default
    raise SystemExit(
        "Could not find docs/grounded_manual. Run init-project first or pass --root."
    )


def resolve_root(root_arg: str | None) -> Path:
    if root_arg:
        root = Path(root_arg)
        if root.name == "grounded_manual":
            return root.resolve()
        return (root / DEFAULT_ROOT).resolve()
    return package_root()


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def git_commit_for(path: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except Exception:
        return "unknown"


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def cjk_ngrams(text: str, min_n: int = 2, max_n: int = 3) -> list[str]:
    grams: list[str] = []
    for seq in re.findall(r"[\u3400-\u9fff]{2,}", text):
        for n in range(min_n, max_n + 1):
            if len(seq) >= n:
                grams.extend(seq[i : i + n] for i in range(len(seq) - n + 1))
    return grams


def index_text(text: str) -> str:
    normalized = normalize_text(text).lower()
    grams = cjk_ngrams(normalized)
    if grams:
        return normalized + "\n" + " ".join(grams)
    return normalized


def query_terms(query: str) -> list[str]:
    normalized = normalize_text(query).lower()
    ascii_words = re.findall(r"[a-z0-9_./:-]{2,}", normalized)
    grams = cjk_ngrams(normalized)
    terms = []
    seen = set()
    for term in [*ascii_words, *grams]:
        if term not in seen:
            seen.add(term)
            terms.append(term)
    if not terms and normalized:
        terms.append(normalized)
    return terms


def fts_query(query: str) -> str:
    terms = query_terms(query)
    if not terms:
        return '""'
    return " OR ".join(f'"{term.replace(chr(34), chr(34) + chr(34))}"' for term in terms)


def split_chunks(text: str, max_chars: int = 1800) -> list[tuple[str, int, int]]:
    lines = text.splitlines()
    chunks: list[tuple[str, int, int]] = []
    buf: list[str] = []
    start = 1
    size = 0
    for idx, line in enumerate(lines, 1):
        if buf and size + len(line) + 1 > max_chars:
            chunks.append(("\n".join(buf).strip(), start, idx - 1))
            buf = []
            size = 0
            start = idx
        buf.append(line)
        size += len(line) + 1
    if buf:
        chunks.append(("\n".join(buf).strip(), start, len(lines) or 1))
    return [(chunk, s, e) for chunk, s, e in chunks if chunk]


def template_project_yaml(project_name: str) -> str:
    return f"""schema_version: {SCHEMA_VERSION}
project_name: {project_name}
default_language: zh
paths:
  sources_manifest: sources/sources.manifest.jsonl
  local_overrides: sources/local_overrides.yaml
  claims: claims/claims.jsonl
  index: index/search.sqlite
policies:
  facts_must_cite_primary_sources: true
  manual_is_not_evidence: true
  default_source_sync_policy: local
  pdf_output_requires_latex: true
"""


def template_lock() -> str:
    obj = {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "tool_commit": git_commit_for(Path(__file__).resolve().parents[1]),
        "python_version": platform.python_version(),
        "created_at": utc_now(),
        "index_config": {
            "engine": "sqlite-fts5",
            "normalization": "NFKC+lowercase+cjk_bigrams_trigrams",
            "chunk_max_chars": 1800,
        },
        "extractors": {"pdf": "pypdf optional"},
    }
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def template_gitignore() -> str:
    return """# Local source mappings and private data
sources/local_overrides.yaml
notes/private_notes.local.md
extracted/local/

# Rebuildable caches and logs
index/
logs/
*.sqlite
*.sqlite-shm
*.sqlite-wal
.env

# Generated or local-only artifacts
manual/*.pdf
manual/*.aux
manual/*.log
manual/*.out
manual/*.toc
manual/*.fls
manual/*.fdb_latexmk
**/.DS_Store
"""


def template_gitattributes() -> str:
    return """# Uncomment if this project intentionally versions PDFs through Git LFS.
# *.pdf filter=lfs diff=lfs merge=lfs -text
"""


def template_sources_manifest() -> str:
    return (
        "# JSONL. Register sources with extract-pdf or by adding records.\n"
        "# sync_policy: public | local | metadata | lfs\n"
    )


def template_claims() -> str:
    return (
        "# JSONL claim registry. Status values: draft, supported, partial, "
        "unsupported, contradicted, stale, needs_review, note.\n"
        "# audit-claims is a locator audit: it can resolve spans and candidates,\n"
        "# but it does not automatically grant semantic support.\n"
    )


def template_public_notes() -> str:
    return """# Public Notes

These notes may be indexed and synced. Mark opinions clearly as personal notes.

"""


def template_private_notes() -> str:
    return """# Private Local Notes

This file is ignored by Git. Use it for private thoughts, local paths, and
research notes that should not be synced.

"""


def template_manual() -> str:
    return """# Friendly Manual

This is a derived manual. It is not a primary evidence source.

## How To Read Citations

- Claims are tracked in `claims/claims.jsonl`.
- Facts should cite PDF pages, source spans, code line ranges, or note locations.
- Personal notes must be labeled as notes, not primary facts.

"""


def init_project(args: argparse.Namespace) -> None:
    root = Path(args.path).resolve() / DEFAULT_ROOT
    root.mkdir(parents=True, exist_ok=True)
    for rel in [
        "sources",
        "extracted/public",
        "extracted/local",
        "claims",
        "notes",
        "manual",
        "index",
        "logs",
    ]:
        (root / rel).mkdir(parents=True, exist_ok=True)

    project_name = args.name or Path(args.path).resolve().name
    writes = {
        "project.yaml": template_project_yaml(project_name),
        "grounded_manual.lock": template_lock(),
        ".gitignore": template_gitignore(),
        ".gitattributes": template_gitattributes(),
        "sources/sources.manifest.jsonl": template_sources_manifest(),
        "sources/local_overrides.yaml": "# Local source path overrides. This file is gitignored.\n",
        "claims/claims.jsonl": template_claims(),
        "notes/public_notes.ai.md": template_public_notes(),
        "notes/private_notes.local.md": template_private_notes(),
        "manual/manual.ai.md": template_manual(),
    }
    created = []
    skipped = []
    for rel, content in writes.items():
        target = root / rel
        if write_text(target, content, force=args.force):
            created.append(rel)
        else:
            skipped.append(rel)
    print(f"Initialized grounded manual project at {root}")
    if created:
        print("Created:")
        for rel in created:
            print(f"  {rel}")
    if skipped:
        print("Skipped existing files:")
        for rel in skipped:
            print(f"  {rel}")


def register_source(root: Path, record: dict) -> None:
    manifest = root / "sources" / "sources.manifest.jsonl"
    rows = [r for r in load_jsonl(manifest) if r.get("source_id") != record["source_id"]]
    rows.append(record)
    dump_jsonl(manifest, rows)


def load_local_overrides(root: Path) -> dict[str, str]:
    path = root / "sources" / "local_overrides.yaml"
    if not path.exists():
        return {}
    overrides: dict[str, str] = {}
    current: str | None = None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.rstrip()
        if re.match(r"^\s{2}[^:#]+:\s*$", line):
            current = line.strip().rstrip(":")
            continue
        if current and "local_path:" in line:
            _, value = line.split("local_path:", 1)
            overrides[current] = value.strip().strip('"').strip("'")
            current = None
    return overrides


def upsert_local_override(root: Path, source_id: str, source_path: Path) -> None:
    overrides = load_local_overrides(root)
    overrides[source_id] = str(source_path)
    lines = [
        "# Local source path overrides. This file is gitignored.",
        "sources:",
    ]
    for sid in sorted(overrides):
        lines.append(f"  {sid}:")
        lines.append(f"    local_path: {overrides[sid]}")
    write_text(root / "sources" / "local_overrides.yaml", "\n".join(lines) + "\n", force=True)


def resolve_source_path(root: Path, source: dict) -> Path | None:
    rel = source.get("relative_path")
    if rel:
        candidate = (root / rel).resolve()
        if candidate.exists():
            return candidate
    overrides = load_local_overrides(root)
    if source.get("source_id") in overrides:
        candidate = Path(overrides[source["source_id"]]).expanduser()
        if candidate.exists():
            return candidate.resolve()
    local = source.get("local_path")
    if local:
        candidate = Path(local).expanduser()
        if candidate.exists():
            return candidate.resolve()
    return None


def extract_pdf(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    pdf = Path(args.pdf).expanduser().resolve()
    if not pdf.exists():
        raise SystemExit(f"PDF not found: {pdf}")
    source_id = args.source_id or pdf.stem.lower().replace(" ", "_")
    sync_policy = args.sync_policy
    inside_root = is_relative_to(pdf, root)
    out_base = root / "extracted" / ("public" if sync_policy in {"public", "lfs"} else "local")
    out_path = out_base / f"{source_id}_pages.md"

    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:
        raise SystemExit(
            "pypdf is required for extract-pdf. Install with: "
            "python -m pip install -r grounded-manual-kit/requirements.lock"
        ) from exc

    reader = PdfReader(str(pdf))
    source_hash = sha256_file(pdf)
    pages = []
    page_hashes = []
    textless_pages = []
    for idx, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        normalized = normalize_text(text)
        if not normalized:
            textless_pages.append(idx)
        phash = sha256_text(normalized)
        page_hashes.append({"page": idx, "text_sha256": phash})
        pages.append(
            "\n".join(
                [
                    f"<!-- source_id: {source_id}; page: {idx}; source_sha256: {source_hash}; text_sha256: {phash} -->",
                    "",
                    normalized,
                    "",
                ]
            )
        )

    write_text(out_path, "\n".join(pages), force=True)
    record = {
        "source_id": source_id,
        "kind": "pdf",
        "file_name": pdf.name,
        "sha256": source_hash,
        "size_bytes": pdf.stat().st_size,
        "mime": "application/pdf",
        "pages": len(reader.pages),
        "sync_policy": sync_policy,
        "path_strategy": "relative" if inside_root else "local_override",
        "relative_path": relpath(pdf, root) if inside_root else None,
        "local_path": None,
        "extracted_path": relpath(out_path, root),
        "extractor": "pypdf",
        "extracted_at": utc_now(),
        "ocr_status": "needs_ocr" if textless_pages else "not_needed",
        "textless_pages": textless_pages,
        "page_hashes": page_hashes,
    }
    register_source(root, record)
    if not inside_root:
        upsert_local_override(root, source_id, pdf)
    print(f"Extracted {len(reader.pages)} pages to {out_path}")
    if textless_pages:
        print(f"Warning: pages with no extractable text: {textless_pages}")


def guess_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".md", ".markdown", ".txt", ".rst"}:
        return "text"
    if suffix in TEXT_SUFFIXES:
        return "code"
    return "file"


def register_source_command(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    path = Path(args.path).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Source not found: {path}")
    source_id = args.source_id or path.stem.lower().replace(" ", "_")
    source_hash = sha256_file(path)
    inside_root = is_relative_to(path, root)
    record = {
        "source_id": source_id,
        "kind": args.kind or guess_kind(path),
        "file_name": path.name,
        "sha256": source_hash,
        "size_bytes": path.stat().st_size,
        "mime": args.mime,
        "sync_policy": args.sync_policy,
        "path_strategy": "relative" if inside_root else "local_override",
        "relative_path": relpath(path, root) if inside_root else None,
        "local_path": None,
        "registered_at": utc_now(),
        "ocr_status": "not_applicable",
    }
    register_source(root, record)
    if not inside_root:
        upsert_local_override(root, source_id, path)
    print(f"Registered {source_id}: {path}")


def parse_page_markers(text: str) -> list[tuple[int | None, str]]:
    marker = re.compile(r"<!--\s*source_id:\s*([^;]+);\s*page:\s*(\d+);[^>]*-->")
    matches = list(marker.finditer(text))
    if not matches:
        return [(None, text)]
    parts: list[tuple[int | None, str]] = []
    for i, match in enumerate(matches):
        page = int(match.group(2))
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        parts.append((page, text[start:end].strip()))
    return parts


def iter_index_docs(root: Path, include_manual: bool = True) -> Iterable[dict]:
    # Extracted evidence.
    for base, public in [(root / "extracted" / "public", True), (root / "extracted" / "local", False)]:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
                continue
            text = read_text(path)
            source_id = path.stem.replace("_pages", "")
            for page, page_text in parse_page_markers(text):
                for chunk, start, end in split_chunks(page_text):
                    yield {
                        "doc_id": f"extracted:{relpath(path, root)}:{page or 0}:{start}-{end}",
                        "source_id": source_id,
                        "source_type": "extracted",
                        "path": relpath(path, root),
                        "title": path.name,
                        "page": page,
                        "line_start": start,
                        "line_end": end,
                        "chunk_hash": sha256_text(chunk),
                        "evidence_allowed": 1,
                        "public": 1 if public else 0,
                        "text": chunk,
                    }

    # Notes. Public and private local notes are both locally queryable, but
    # private notes carry public=0 metadata.
    note_files = [
        (root / "notes" / "public_notes.ai.md", 1),
        (root / "notes" / "private_notes.local.md", 0),
    ]
    for path, public in note_files:
        if path.exists():
            text = read_text(path)
            for chunk, start, end in split_chunks(text):
                yield {
                    "doc_id": f"note:{relpath(path, root)}:{start}-{end}",
                    "source_id": path.stem,
                    "source_type": "note",
                    "path": relpath(path, root),
                    "title": path.name,
                    "page": None,
                    "line_start": start,
                    "line_end": end,
                    "chunk_hash": sha256_text(chunk),
                    "evidence_allowed": 1,
                    "public": public,
                    "text": chunk,
                }

    # Registered local text/code sources.
    for source in load_jsonl(root / "sources" / "sources.manifest.jsonl"):
        path = resolve_source_path(root, source)
        if not path or not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if "extracted/" in relpath(path, root):
            continue
        text = read_text(path)
        for chunk, start, end in split_chunks(text):
                yield {
                    "doc_id": f"source:{source.get('source_id')}:{start}-{end}",
                    "source_id": source.get("source_id"),
                    "source_type": source.get("kind", "source"),
                    "path": source.get("relative_path") or source.get("file_name") or str(path),
                    "title": path.name,
                "page": None,
                "line_start": start,
                "line_end": end,
                "chunk_hash": sha256_text(chunk),
                "evidence_allowed": 1,
                "public": 1 if source.get("sync_policy") in {"public", "lfs"} else 0,
                "text": chunk,
            }

    # Derived manual is searchable for navigation only, not evidence.
    if include_manual:
        path = root / "manual" / "manual.ai.md"
        if path.exists():
            text = read_text(path)
            for chunk, start, end in split_chunks(text):
                yield {
                    "doc_id": f"manual:{relpath(path, root)}:{start}-{end}",
                    "source_id": "manual",
                    "source_type": "manual",
                    "path": relpath(path, root),
                    "title": path.name,
                    "page": None,
                    "line_start": start,
                    "line_end": end,
                    "chunk_hash": sha256_text(chunk),
                    "evidence_allowed": 0,
                    "public": 1,
                    "text": chunk,
                }


def ensure_db_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        DROP TABLE IF EXISTS docs;
        DROP TABLE IF EXISTS docs_fts;
        CREATE TABLE docs (
            doc_id TEXT PRIMARY KEY,
            source_id TEXT,
            source_type TEXT,
            path TEXT,
            title TEXT,
            page INTEGER,
            line_start INTEGER,
            line_end INTEGER,
            chunk_hash TEXT,
            evidence_allowed INTEGER NOT NULL,
            public INTEGER NOT NULL,
            text TEXT NOT NULL,
            normalized_text TEXT NOT NULL,
            metadata_json TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE docs_fts USING fts5(
            doc_id UNINDEXED,
            normalized_text,
            text,
            tokenize='unicode61'
        );
        """
    )


def build_index(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    db_path = root / "index" / "search.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    ensure_db_schema(con)
    count = 0
    for doc in iter_index_docs(root, include_manual=True):
        normalized = index_text(doc["text"])
        metadata = {k: v for k, v in doc.items() if k != "text"}
        con.execute(
            """
            INSERT INTO docs (
                doc_id, source_id, source_type, path, title, page, line_start,
                line_end, chunk_hash, evidence_allowed, public, text,
                normalized_text, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc["doc_id"],
                doc.get("source_id"),
                doc.get("source_type"),
                doc.get("path"),
                doc.get("title"),
                doc.get("page"),
                doc.get("line_start"),
                doc.get("line_end"),
                doc.get("chunk_hash"),
                int(doc.get("evidence_allowed", 1)),
                int(doc.get("public", 0)),
                doc["text"],
                normalized,
                json.dumps(metadata, ensure_ascii=False, sort_keys=True),
            ),
        )
        con.execute(
            "INSERT INTO docs_fts (doc_id, normalized_text, text) VALUES (?, ?, ?)",
            (doc["doc_id"], normalized, doc["text"]),
        )
        count += 1
    con.commit()
    con.close()
    print(f"Indexed {count} chunks into {db_path}")


def search(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    db_path = root / "index" / "search.sqlite"
    if not db_path.exists():
        raise SystemExit(f"Index not found: {db_path}. Run build-index first.")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    query = fts_query(args.query)
    evidence_clause = "" if args.include_manual else "AND docs.evidence_allowed = 1"
    sql = f"""
        SELECT docs.*, bm25(docs_fts) AS rank
        FROM docs_fts
        JOIN docs ON docs.doc_id = docs_fts.doc_id
        WHERE docs_fts MATCH ? {evidence_clause}
        ORDER BY rank
        LIMIT ?
    """
    try:
        rows = con.execute(sql, (query, args.limit)).fetchall()
    except sqlite3.OperationalError:
        rows = []
    if not rows:
        like = f"%{normalize_text(args.query).lower()}%"
        sql_like = f"""
            SELECT docs.*, 0 AS rank
            FROM docs
            WHERE docs.normalized_text LIKE ? {evidence_clause}
            LIMIT ?
        """
        rows = con.execute(sql_like, (like, args.limit)).fetchall()

    if args.json:
        print(
            json.dumps(
                [dict(row) | {"metadata": json.loads(row["metadata_json"])} for row in rows],
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for i, row in enumerate(rows, 1):
            loc = row["path"]
            if row["page"]:
                loc += f" p.{row['page']}"
            elif row["line_start"]:
                loc += f":{row['line_start']}"
            print(f"[{i}] {row['source_type']} {loc} ({row['chunk_hash'][:12]})")
            snippet = re.sub(r"\s+", " ", row["text"]).strip()
            print(textwrap.shorten(snippet, width=args.width, placeholder=" ..."))
            print()
    con.close()


def verify_sources(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    rows = load_jsonl(root / "sources" / "sources.manifest.jsonl")
    changed: set[str] = set()
    missing: set[str] = set()
    for source in rows:
        sid = source.get("source_id", "<missing>")
        path = resolve_source_path(root, source)
        if not path:
            missing.add(sid)
            print(f"MISSING {sid}: {source.get('file_name')}")
            continue
        digest = sha256_file(path)
        if digest != source.get("sha256"):
            changed.add(sid)
            print(f"STALE {sid}: expected {source.get('sha256')} got {digest}")
        else:
            print(f"OK {sid}: {path}")

    if args.mark_stale and changed:
        claims_path = root / "claims" / "claims.jsonl"
        claims = load_jsonl(claims_path)
        touched = 0
        for claim in claims:
            spans = claim.get("source_spans", []) or claim.get("sources", [])
            span_ids = {span.get("source_id") for span in spans if isinstance(span, dict)}
            if span_ids & changed:
                claim["status"] = "stale"
                claim["stale_reason"] = "source_hash_changed"
                claim["updated_at"] = utc_now()
                touched += 1
        dump_jsonl(claims_path, claims)
        print(f"Marked {touched} claims stale.")

    if missing:
        raise SystemExit(2)
    if changed:
        raise SystemExit(3)


AUDIT_OVERWRITABLE_STATUSES = {"draft", "needs_review", "unsupported"}
AUDIT_PRESERVED_STATUSES = {"supported", "partial", "contradicted", "stale"}


def span_chunk_hash(span: dict) -> object | None:
    return span.get("chunk_hash") or span.get("span_hash")


def span_line_bounds(span: dict) -> tuple[object | None, object | None]:
    line_start = span.get("line_start")
    if line_start is None:
        line_start = span.get("start_line")
    if line_start is None:
        line_start = span.get("line")
    line_end = span.get("line_end")
    if line_end is None:
        line_end = span.get("end_line")
    if line_end is None:
        line_end = line_start
    return line_start, line_end


def span_has_precise_locator(span: dict) -> bool:
    line_start, line_end = span_line_bounds(span)
    return (
        span.get("page") is not None
        or span_chunk_hash(span) is not None
        or (line_start is not None and line_end is not None)
    )


def audit_hit(row: sqlite3.Row | dict, hit_type: str) -> dict:
    return {
        "hit_type": hit_type,
        "doc_id": row["doc_id"],
        "source_id": row["source_id"],
        "path": row["path"],
        "page": row["page"],
        "line_start": row["line_start"],
        "line_end": row["line_end"],
        "chunk_hash": row["chunk_hash"],
    }


def resolve_precise_span(con: sqlite3.Connection, span: dict) -> sqlite3.Row | None:
    sid = span.get("source_id")
    if not sid or not span_has_precise_locator(span):
        return None
    page = span.get("page")
    chunk_hash = span_chunk_hash(span)
    line_start, line_end = span_line_bounds(span)
    clauses = ["source_id = ?", "evidence_allowed = 1"]
    params: list[object] = [sid]
    if page is not None:
        clauses.append("page = ?")
        params.append(page)
    if chunk_hash:
        clauses.append("chunk_hash = ?")
        params.append(chunk_hash)
    if line_start is not None and line_end is not None:
        clauses.append("line_start <= ?")
        clauses.append("line_end >= ?")
        params.extend([line_end, line_start])
    return con.execute(
        f"SELECT * FROM docs WHERE {' AND '.join(clauses)} LIMIT 1", params
    ).fetchone()


def audit_claims(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    db_path = root / "index" / "search.sqlite"
    if not db_path.exists():
        raise SystemExit(f"Index not found: {db_path}. Run build-index first.")
    claims_path = root / "claims" / "claims.jsonl"
    claims = load_jsonl(claims_path)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    audited = []
    for claim in claims:
        if not claim.get("id"):
            continue
        status_before = claim.get("status") or "draft"
        audited_at = utc_now()
        if status_before == "note":
            audit = {
                "claim_id": claim.get("id"),
                "status": "skipped_note",
                "audit_result": "skipped_note",
                "claim_status_before": status_before,
                "claim_status_after": status_before,
                "write_action": "skipped",
                "reason": "note claims are not locator-audited",
                "audited_at": audited_at,
                "tool": TOOL_NAME,
                "tool_version": TOOL_VERSION,
                "query_terms": [],
                "hits": [],
            }
            audited.append(audit)
            print(f"{claim.get('id')}: skipped_note - {audit['reason']}")
            continue

        text = claim.get("text", "")
        spans = claim.get("source_spans", []) or claim.get("sources", [])
        precise_spans = []
        source_only_spans = []
        span_hits = []
        for span in spans:
            if not isinstance(span, dict):
                continue
            if not span.get("source_id"):
                continue
            if span_has_precise_locator(span):
                precise_spans.append(span)
            else:
                source_only_spans.append(span)
                continue
            found = resolve_precise_span(con, span)
            if found:
                span_hits.append(found)

        if span_hits:
            audit_result = "needs_review"
            if len(span_hits) == len(precise_spans) and not source_only_spans:
                reason = "span resolved, semantic support not checked"
            elif source_only_spans:
                reason = "some precise spans resolved; source-only spans are weak locators; semantic support not checked"
            else:
                reason = "some precise spans resolved; semantic support not checked"
            hit_rows = [audit_hit(row, "span_resolved") for row in span_hits]
            terms = []
        else:
            terms = query_terms(text)
            query = fts_query(text)
            try:
                rows = con.execute(
                    """
                    SELECT docs.*
                    FROM docs_fts
                    JOIN docs ON docs.doc_id = docs_fts.doc_id
                    WHERE docs_fts MATCH ? AND docs.evidence_allowed = 1
                    LIMIT 3
                    """,
                    (query,),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []
            if rows:
                audit_result = "needs_review"
                if source_only_spans and not precise_spans:
                    reason = "declared spans only named source_id; source-only locator is not a precise span; text search found possible evidence"
                elif precise_spans:
                    reason = "declared precise spans did not resolve; text search found possible evidence"
                else:
                    reason = "text search found possible evidence, but no declared span resolved"
                hit_rows = [audit_hit(row, "fts_candidate") for row in rows]
            else:
                audit_result = "unsupported"
                if source_only_spans and not precise_spans:
                    reason = "declared spans only named source_id; source-only locator is not a precise span; no text-search evidence found"
                elif precise_spans:
                    reason = "declared precise spans did not resolve and no text-search evidence found"
                else:
                    reason = "no declared span or text-search evidence found"
                hit_rows = []

        if not args.write:
            status_after = status_before
            write_action = "not_written"
        elif status_before in AUDIT_OVERWRITABLE_STATUSES:
            status_after = audit_result
            write_action = "updated"
        elif status_before in AUDIT_PRESERVED_STATUSES:
            status_after = status_before
            write_action = "preserved"
        else:
            status_after = status_before
            write_action = "preserved_unknown_status"

        audit = {
            "claim_id": claim.get("id"),
            "status": audit_result,
            "audit_result": audit_result,
            "claim_status_before": status_before,
            "claim_status_after": status_after,
            "write_action": write_action,
            "reason": reason,
            "audited_at": audited_at,
            "tool": TOOL_NAME,
            "tool_version": TOOL_VERSION,
            "query_terms": terms,
            "hits": hit_rows,
        }
        audited.append(audit)
        suffix = f" -> {status_after}" if status_after != audit_result else ""
        print(f"{claim.get('id')}: {audit_result}{suffix} - {reason}")
        if args.write:
            if write_action == "updated":
                claim["status"] = status_after
                claim["last_audited_at"] = audit["audited_at"]
                claim["audit_reason"] = reason
            elif write_action in {"preserved", "preserved_unknown_status"}:
                claim["last_audited_at"] = audit["audited_at"]

    con.close()
    log_path = root / "logs" / f"audit_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    dump_jsonl(log_path, audited)
    if args.write:
        dump_jsonl(claims_path, claims)
        print(f"Updated {claims_path}")
    print(f"Wrote audit log {log_path}")


def latex_escape(text: str) -> str:
    repl = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(repl.get(ch, ch) for ch in text)


def markdown_to_simple_latex(md: str) -> str:
    lines = []
    in_itemize = False
    for raw in md.splitlines():
        line = raw.rstrip()
        if line.startswith("# "):
            if in_itemize:
                lines.append(r"\end{itemize}")
                in_itemize = False
            lines.append(r"\section*{" + latex_escape(line[2:].strip()) + "}")
        elif line.startswith("## "):
            if in_itemize:
                lines.append(r"\end{itemize}")
                in_itemize = False
            lines.append(r"\subsection*{" + latex_escape(line[3:].strip()) + "}")
        elif line.startswith("### "):
            if in_itemize:
                lines.append(r"\end{itemize}")
                in_itemize = False
            lines.append(r"\subsubsection*{" + latex_escape(line[4:].strip()) + "}")
        elif line.startswith("- "):
            if not in_itemize:
                lines.append(r"\begin{itemize}")
                in_itemize = True
            lines.append(r"\item " + latex_escape(line[2:].strip()))
        elif not line:
            if in_itemize:
                lines.append(r"\end{itemize}")
                in_itemize = False
            lines.append("")
        else:
            if in_itemize:
                lines.append(r"\end{itemize}")
                in_itemize = False
            lines.append(latex_escape(line) + "\n")
    if in_itemize:
        lines.append(r"\end{itemize}")
    return "\n".join(lines)


def render(args: argparse.Namespace) -> None:
    root = resolve_root(args.root)
    md_path = root / "manual" / "manual.ai.md"
    tex_path = root / "manual" / "manual.tex"
    pdf_path = root / "manual" / "manual.pdf"
    if not md_path.exists():
        raise SystemExit(f"Manual not found: {md_path}")

    engine = next((cmd for cmd in ["xelatex", "tectonic", "latexmk", "pdflatex"] if command_exists(cmd)), None)
    if not engine and not args.tex_only:
        print("No LaTeX engine found; leaving manual.ai.md as the active output.")
        return

    body = markdown_to_simple_latex(read_text(md_path))
    tex = rf"""\documentclass[11pt]{{article}}
\usepackage{{geometry}}
\usepackage{{hyperref}}
\geometry{{margin=1in}}
\begin{{document}}
{body}
\end{{document}}
"""
    write_text(tex_path, tex, force=True)
    print(f"Wrote {tex_path}")
    if args.tex_only:
        return

    if engine == "tectonic":
        cmd = [engine, tex_path.name]
    elif engine == "latexmk":
        cmd = [engine, "-pdf", "-interaction=nonstopmode", tex_path.name]
    else:
        cmd = [engine, "-interaction=nonstopmode", tex_path.name]
    print(f"Running {' '.join(cmd)} in {tex_path.parent}")
    result = subprocess.run(cmd, cwd=tex_path.parent)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    if pdf_path.exists():
        meta = {
            "rendered_at": utc_now(),
            "engine": engine,
            "manual_ai_md_sha256": sha256_file(md_path),
            "manual_tex_sha256": sha256_file(tex_path),
            "manual_pdf_sha256": sha256_file(pdf_path),
        }
        write_text(root / "manual" / "manual.render.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n", force=True)
        print(f"Wrote {pdf_path}")


def doctor(args: argparse.Namespace) -> None:
    root = Path(args.root).resolve() if args.root else None
    print(f"{TOOL_NAME} {TOOL_VERSION}")
    print(f"Python: {platform.python_version()} ({sys.executable})")
    print(f"Platform: {platform.platform()}")
    sqlite_ok = False
    try:
        con = sqlite3.connect(":memory:")
        con.execute("CREATE VIRTUAL TABLE docs USING fts5(text)")
        sqlite_ok = True
        con.close()
    except Exception as exc:
        print(f"SQLite FTS5: no ({exc})")
    if sqlite_ok:
        print(f"SQLite FTS5: yes ({sqlite3.sqlite_version})")
    try:
        import pypdf  # type: ignore

        print(f"pypdf: yes ({getattr(pypdf, '__version__', 'unknown')})")
    except Exception:
        print("pypdf: no (PDF extraction disabled until installed)")
    print(f"git: {'yes' if command_exists('git') else 'no'}")
    print(f"git-lfs: {'yes' if command_exists('git-lfs') or _git_lfs_available() else 'no'}")
    latex = [cmd for cmd in ["xelatex", "latexmk", "tectonic", "pdflatex"] if command_exists(cmd)]
    print(f"LaTeX engines: {', '.join(latex) if latex else 'none'}")
    ocr = [cmd for cmd in ["ocrmypdf", "tesseract"] if command_exists(cmd)]
    print(f"OCR tools: {', '.join(ocr) if ocr else 'none'}")
    if root and (root / "project.yaml").exists():
        print(f"Project root: {root}")
        manifest = root / "sources" / "sources.manifest.jsonl"
        sources = load_jsonl(manifest)
        print(f"Registered sources: {len(sources)}")
        missing = 0
        for source in sources:
            if not resolve_source_path(root, source):
                missing += 1
        print(f"Missing sources: {missing}")
    elif root:
        print(f"Project root not initialized: {root}")


def _git_lfs_available() -> bool:
    try:
        subprocess.check_output(["git", "lfs", "version"], stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Grounded manual evidence-pack toolkit")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init-project", help="create docs/grounded_manual in a project")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--name")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=init_project)

    p = sub.add_parser("extract-pdf", help="extract a PDF into page-marked markdown")
    p.add_argument("pdf")
    p.add_argument("--root")
    p.add_argument("--source-id")
    p.add_argument("--sync-policy", choices=["public", "local", "metadata", "lfs"], default="local")
    p.set_defaults(func=extract_pdf)

    p = sub.add_parser("register-source", help="register a text/code/source file in the manifest")
    p.add_argument("path")
    p.add_argument("--root")
    p.add_argument("--source-id")
    p.add_argument("--kind")
    p.add_argument("--mime", default="text/plain")
    p.add_argument("--sync-policy", choices=["public", "local", "metadata", "lfs"], default="local")
    p.set_defaults(func=register_source_command)

    p = sub.add_parser("build-index", help="rebuild SQLite FTS index")
    p.add_argument("--root")
    p.set_defaults(func=build_index)

    p = sub.add_parser("search", help="search the local evidence index")
    p.add_argument("query")
    p.add_argument("--root")
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--width", type=int, default=220)
    p.add_argument("--include-manual", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=search)

    p = sub.add_parser("verify-sources", help="verify source hashes and optionally mark claims stale")
    p.add_argument("--root")
    p.add_argument("--mark-stale", action="store_true")
    p.set_defaults(func=verify_sources)

    p = sub.add_parser("audit-claims", help="audit claim spans without using manual as evidence")
    p.add_argument("--root")
    p.add_argument("--write", action="store_true", help="write audit statuses back to claims.jsonl")
    p.set_defaults(func=audit_claims)

    p = sub.add_parser("render", help="render manual.ai.md to LaTeX/PDF when tools exist")
    p.add_argument("--root")
    p.add_argument("--tex-only", action="store_true")
    p.set_defaults(func=render)

    p = sub.add_parser("doctor", help="check local runtime and optional project health")
    p.add_argument("--root")
    p.set_defaults(func=doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
