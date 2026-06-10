---
name: grounded-manual
description: Use when building or querying a local source-grounded evidence pack for PDFs, source code, notes, and friendly manuals; includes project initialization, PDF extraction, SQLite FTS indexing, strict citation-aware answering, manual drafting, and optional LaTeX/PDF rendering without treating manuals as primary evidence.
metadata:
  short-description: Build and query source-grounded manual packs
---

# Grounded Manual

Use this skill when the user wants a reusable, local, citation-grounded manual
or wants answers from a `docs/grounded_manual/` evidence pack.

## Pack Lookup

When selecting a pack, prefer the closest explicit or current-project evidence
pack before using the local registry.

Selection order:

1. If the user gives an exact `docs/grounded_manual` path, use it after checking
   that `project.yaml` exists.
2. If the user gives a project root path, use its `docs/grounded_manual` after
   checking that `project.yaml` exists.
3. Check the current directory and its parents for
   `docs/grounded_manual/project.yaml`.
4. Use the local evidence-pack registry only when no current-project pack is
   found, or when the user names a project, software package, topic, or alias
   that should be resolved outside the current project.

Registry lookup order:

1. Path in `GROUNDED_MANUAL_REGISTRY`, if set.
2. `~/.codex/grounded-manual/packs.local.yaml`.
3. `manual_packs.local.yaml` in the `grounded-manual-kit` directory.

The registry is a routing table, not evidence. Use it only to select a pack.
Then answer from that pack's original sources, extracted spans, code spans,
notes, or claims.

Registry behavior:

- Ignore entries where `enabled` is false.
- Match by `id`, `aliases`, `description`, or `tags`.
- Use `pack_root` when present.
- If only `project_root` is present, use `project_root/docs/grounded_manual`.
- After resolving a pack root, verify that `project.yaml` exists there. If it
  does not, treat the registry entry as stale and ask for an updated path.
- Say which pack was selected before answering.
- Ask the user when multiple enabled packs match equally well.
- Do not expose local absolute paths in final answers unless the user asks.

## Core Rule

Do not treat `manual/manual.ai.md`, `manual/manual.tex`, or `manual/manual.pdf`
as fact evidence. They are derived manuals. Facts must resolve to primary
sources, extracted evidence, code spans, notes, or claim records.

Evidence hierarchy:

1. Primary sources: PDFs, source code, original text files, original notes.
2. Extracted evidence: `extracted/public/**` and `extracted/local/**` with page,
   line, chunk, and hash metadata.
3. Claims: `claims/claims.jsonl` with source spans and audit status.
4. Derived outputs: `manual/**`; use only for navigation and readability.
5. Index: `index/search.sqlite`; a rebuildable cache.

## Expected Project Layout

```text
docs/grounded_manual/
├── project.yaml
├── grounded_manual.lock
├── sources/sources.manifest.jsonl
├── sources/local_overrides.yaml
├── extracted/public/
├── extracted/local/
├── claims/claims.jsonl
├── notes/public_notes.ai.md
├── notes/private_notes.local.md
├── manual/manual.ai.md
└── index/search.sqlite
```

## Tooling

Prefer the toolkit CLI:

```bash
grounded-manual doctor
grounded-manual init-project .
grounded-manual extract-pdf path/to/file.pdf --source-id manual --sync-policy local
grounded-manual register-source path/to/source.m --source-id source_m --kind code
grounded-manual build-index
grounded-manual search "question terms"
grounded-manual verify-sources --mark-stale
grounded-manual render
```

If the command is not installed, run the script directly:

```bash
python grounded-manual-kit/scripts/grounded_manual.py <command>
```

## Answering Workflow

1. Select the pack using the lookup order above.
2. Run or request `grounded-manual build-index` if `index/search.sqlite` is
   missing or stale.
3. Search the evidence layer. Use `--include-manual` only to locate explanatory
   sections, never to prove facts.
4. Cite PDF page, source path and line, chunk id/hash, or note path.
5. Label user notes as personal notes, interpretation, or experience.
6. If no source supports the claim, say that no indexed source was found.

Recommended answer shape:

```text
结论：
...

出处：
- source.pdf, p.N
- path/to/file.ext:line

个人笔记：
- notes/public_notes.ai.md or private_notes.local.md, clearly labeled
```

## Manual Drafting Workflow

- Draft `manual/manual.ai.md` from resolved claims and evidence.
- Keep claim metadata in `claims/claims.jsonl`; do not hide audit state in the
  manual body.
- If a claim has no reliable source span, mark it as `draft` or
  `needs_review`, not as fact.
- Preserve clear labels for personal notes.

## Cross-Platform Rules

- Use relative paths in `project.yaml` and manifests.
- Put machine-specific paths in `sources/local_overrides.yaml`; this file is
  ignored by Git.
- Rebuild `index/search.sqlite` per platform.
- Run `grounded-manual doctor` after moving between Windows, WSL, Linux, or
  macOS.

## LaTeX/PDF

If a LaTeX-focused skill exists, use it only for rendering frozen manual
content. Do not allow rendering work to add claims, remove citations, or change
claim audit status.
