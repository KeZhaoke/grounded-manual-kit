# AI Agent Quickstart: Build a Grounded Manual Pack

This file is for a local AI agent. Use it when the user is inside a project
folder and asks you to build a source-grounded manual/search pack from PDFs,
source code, text files, and notes.

## What This System Is

`grounded-manual-kit` is a local evidence-pack workflow. The scripts are
deterministic tools; the AI agent decides when to run them, interprets results,
drafts claims/manuals, and answers questions using citations.

Do not treat `manual/manual.ai.md`, `manual/manual.tex`, or
`manual/manual.pdf` as primary evidence. They are derived outputs.

Primary evidence is:

- registered original sources
- extracted page/line/chunk text
- source code spans
- user notes, clearly labeled as notes
- `claims/claims.jsonl` plus its source spans and audit state

`grounded-manual audit-claims` is a locator audit. It can check whether declared
spans resolve and can find candidate evidence, but it does not automatically
confirm semantic support. Claims marked `supported`, `partial`,
`contradicted`, or `stale` should be treated as human or external review
states, not as statuses granted by the locator audit.

## First Actions In A Project Folder

1. Check whether the toolkit command exists:

   ```bash
   grounded-manual doctor
   ```

   If unavailable, look for `grounded-manual-kit/` nearby or ask the user where
   it is installed. Do not invent paths.

2. Check whether this project already has a pack:

   ```bash
   test -f docs/grounded_manual/project.yaml && echo exists
   ```

3. If no pack exists, initialize:

   ```bash
   grounded-manual init-project .
   ```

4. Ask for source files only if they cannot be discovered. Otherwise register
   obvious PDFs, Markdown, text, and source files conservatively.

## Common Build Commands

Register a text/source file:

```bash
grounded-manual register-source path/to/file.md --source-id file_id --kind text --sync-policy local
```

Extract a PDF:

```bash
grounded-manual extract-pdf path/to/manual.pdf --source-id manual --sync-policy local
```

Build or rebuild the local index:

```bash
grounded-manual build-index
```

Search evidence:

```bash
grounded-manual search "query terms"
```

Audit claims:

```bash
grounded-manual audit-claims
```

Render manual if LaTeX exists:

```bash
grounded-manual render
```

## Windows PowerShell Equivalents

```powershell
grounded-manual doctor
grounded-manual init-project .
grounded-manual extract-pdf .\manual.pdf --source-id manual --sync-policy local
grounded-manual build-index
grounded-manual search "安装"
```

## How To Draft Claims

Add facts to `docs/grounded_manual/claims/claims.jsonl` as JSONL. Keep one
claim per line.

Minimal claim:

```json
{"id":"C-001","text":"The manual states ...","status":"draft","source_spans":[{"source_id":"manual","page":3}]}
```

When possible, include chunk hashes from search results:

```json
{"id":"C-002","text":"...","status":"draft","source_spans":[{"source_id":"manual","page":3,"chunk_hash":"abc123..."}]}
```

Run:

```bash
grounded-manual audit-claims --write
```

After `--write`, precise span matches normally become `needs_review` with an
audit reason such as `span resolved, semantic support not checked`. A `note`
claim is skipped by the locator audit, and existing `supported`, `partial`,
`contradicted`, or `stale` statuses are preserved by default.

## How To Answer User Questions

Use this response shape:

```text
结论：
...

出处：
- source.pdf, p.N
- path/to/file.ext:line

个人笔记：
- Clearly label user notes or interpretation.
```

Rules:

- Search evidence first.
- Use `manual.ai.md` only to locate friendly explanations, not to prove facts.
- If no evidence is found, say so plainly.
- Never convert private notes into primary facts.
- Do not include local absolute paths in final answers unless the user asks for
  local file locations.

## Cross-Platform Notes

- `index/search.sqlite` is a local cache. Rebuild it on Windows, WSL, Linux, or
  macOS after moving a project.
- Put platform-specific paths in
  `docs/grounded_manual/sources/local_overrides.yaml`; it is ignored by Git.
- If `pypdf` is missing, PDF extraction will fail with an install hint.
- If LaTeX is missing, keep `manual.ai.md` as the active output.
