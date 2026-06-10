# Asking Codex About Grounded Manuals

This guide is for humans talking to Codex, or another local AI agent, while
working with a `grounded-manual-kit` evidence pack.

Use it when you know what you want, but not the exact command. The most useful
prompt shape is:

```text
Use <skill or workflow> to <action> for <files or topic>. <constraints>.
```

You can ask in any language. The important part is to name the task, the target
files or topic, and whether Codex is allowed to edit files.

## When To Name A Skill

Use `grounded-manual` when you want to build, update, search, or answer from an
evidence pack:

```text
Use grounded-manual to search the evidence pack for installation steps and
answer with citations.
```

Use `citation-auditor` when you want to verify, challenge, or update claim
statuses:

```text
Use citation-auditor to audit claims.jsonl and report unsupported claims.
Do not write changes.
```

If you only want advice, say that explicitly:

```text
Discuss only. Do not edit files or run commands that write files.
```

## Important Boundaries

- Original sources, extracted spans, source code, notes, and claim records can
  support answers.
- `manual/manual.ai.md`, `manual/manual.tex`, and `manual/manual.pdf` are
  derived outputs. They are useful for navigation, but they do not prove facts.
- Private notes can be searched locally, but they should be labeled as notes,
  interpretation, or experience.
- If no indexed source supports an answer, Codex should say so plainly.
- `index/search.sqlite` is a rebuildable local cache. Rebuild it after moving a
  project or changing sources.

## Local Evidence Pack Registry

If you maintain several grounded-manual packs on the same machine, you can keep
a local registry so Codex can find the right pack before searching evidence.

Start from `manual_packs.example.yaml`, then copy it to a local-only file such
as:

```text
manual_packs.local.yaml
~/.codex/grounded-manual/packs.local.yaml
```

The registry is a routing table, not an evidence source. It can help Codex find
`project_root` or `pack_root`, but answers must still cite the selected pack's
sources, extracted spans, notes, or claims.

Suggested lookup order:

1. `GROUNDED_MANUAL_REGISTRY`
2. `~/.codex/grounded-manual/packs.local.yaml`
3. `manual_packs.local.yaml` in the `grounded-manual-kit` directory

Ask:

```text
Use the local grounded-manual registry to find grounded-manual-kit, then answer:
how do I add a PDF? Cite the selected pack's evidence.
```

Or:

```text
Look in the local grounded-manual registry for packs related to citation audit.
If more than one pack matches, ask me which one to use.
```

Codex should:

- Ignore registry entries where `enabled` is false.
- Match by `id`, `aliases`, `description`, or `tags`.
- Use `pack_root` when present.
- Use `project_root/docs/grounded_manual` when only `project_root` is present.
- Say which pack it selected before answering.
- Ask when multiple packs match.
- Avoid exposing local absolute paths in final answers unless you ask for them.

Files that may change:

- `manual_packs.local.yaml` if you ask Codex to update the local registry
- `~/.codex/grounded-manual/packs.local.yaml` if you keep the registry there

## Common Requests

### Add A PDF

Ask:

```text
Use grounded-manual to add path/to/manual.pdf to the evidence pack with
source-id manual, then rebuild the index.
```

Codex should:

- Check that `docs/grounded_manual/project.yaml` exists.
- Run `extract-pdf` with the requested `source-id` and sync policy.
- Rebuild the search index.

Files that may change:

- `docs/grounded_manual/sources/sources.manifest.jsonl`
- `docs/grounded_manual/extracted/public/` or `extracted/local/`
- `docs/grounded_manual/index/search.sqlite`
- `docs/grounded_manual/sources/local_overrides.yaml` for local-only paths

Codex may need confirmation when the PDF contains private data, the source ID
is unclear, or the source should be synced publicly.

### Register Source Code Or Text

Ask:

```text
Use grounded-manual to register src/example.py as source-id example_py with
kind code, then rebuild the index.
```

Codex should register the file in the manifest and rebuild the index.

Files that may change:

- `docs/grounded_manual/sources/sources.manifest.jsonl`
- `docs/grounded_manual/index/search.sqlite`
- `docs/grounded_manual/sources/local_overrides.yaml` for local-only paths

### Search Evidence And Answer

Ask:

```text
Use grounded-manual to answer: how do I rebuild the index? Cite the evidence.
```

Codex should search the evidence layer first and cite PDF pages, source paths,
line numbers, chunk IDs, or note paths. It should not use the derived manual as
proof.

Files normally changed: none.

If the index is missing or stale, Codex may rebuild it before answering.

### Audit Claims

Ask:

```text
Use citation-auditor to audit claims.jsonl. Report partial, unsupported, stale,
or contradicted claims. Do not write changes.
```

Codex should resolve each claim's declared source spans first, search evidence
only when needed, and report problems with suggested fixes.

Files that may change:

- `docs/grounded_manual/logs/` when the audit command writes an audit log

Add `--write` intent only when you want claim statuses updated:

```text
Use citation-auditor to audit claims.jsonl and write updated statuses.
```

Files that may also change:

- `docs/grounded_manual/claims/claims.jsonl`

### Sources Changed

Ask:

```text
Use grounded-manual to verify sources, mark stale claims, rebuild the index, and
tell me what needs review.
```

Codex should run source verification, mark claims stale if source hashes
changed, rebuild the index, and optionally audit claims.

Files that may change:

- `docs/grounded_manual/claims/claims.jsonl`
- `docs/grounded_manual/index/search.sqlite`
- `docs/grounded_manual/logs/`

### Update The Friendly Manual

Ask:

```text
Use grounded-manual to update manual/manual.ai.md from supported claims and
evidence. Mark anything without reliable support as draft or needs_review.
```

Codex should draft from evidence and claim records. It should not let the
existing manual prove new facts.

Files that may change:

- `docs/grounded_manual/manual/manual.ai.md`
- `docs/grounded_manual/claims/claims.jsonl` if claim metadata needs updates

### Add Notes

Ask:

```text
Add this as a public note, clearly labeled as my interpretation, then rebuild
the index.
```

Or:

```text
Add this to private local notes only. Do not sync it.
```

Codex should keep notes clearly labeled and avoid turning private notes into
primary facts.

Files that may change:

- `docs/grounded_manual/notes/public_notes.ai.md`
- `docs/grounded_manual/notes/private_notes.local.md`
- `docs/grounded_manual/index/search.sqlite`

### Move Across Machines

Ask:

```text
Use grounded-manual to check this project after moving machines. Verify sources
and rebuild the index.
```

Codex should run `doctor`, check local overrides, verify source hashes, and
rebuild the local index.

Files that may change:

- `docs/grounded_manual/sources/local_overrides.yaml`
- `docs/grounded_manual/index/search.sqlite`
- `docs/grounded_manual/claims/claims.jsonl` if stale claims are marked

### Render The Manual

Ask:

```text
Use grounded-manual to render the manual. If LaTeX is unavailable, leave
manual.ai.md as the active output and tell me.
```

Codex should render only the current manual content. Rendering should not add
claims, remove citations, or change audit status.

Files that may change:

- `docs/grounded_manual/manual/manual.tex`
- `docs/grounded_manual/manual/manual.pdf`
- `docs/grounded_manual/manual/manual.render.json`
- LaTeX auxiliary files under `docs/grounded_manual/manual/`

### Discuss Before Editing

Ask:

```text
I want to discuss the approach first. Do not edit files yet.
```

Codex should answer with tradeoffs, possible workflows, and risks. It should
wait for a direct request before changing files.

Files changed: none.

## Good Constraints To Add

- `Do not edit files.`
- `Do not write claim statuses yet.`
- `Use --write if the audit supports it.`
- `Use source-id <name>.`
- `Treat this file as private/local only.`
- `Answer in Chinese.`
- `Only cite indexed evidence.`
- `If evidence is missing, say no indexed source was found.`
