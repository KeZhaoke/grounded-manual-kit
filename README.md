# grounded-manual-kit

Reusable local evidence-pack tooling for source-grounded manuals.

## Install

Unix, Linux, macOS, or WSL:

```bash
./install.sh
python3 -m pip install -r requirements.lock
grounded-manual doctor
```

Windows PowerShell:

```powershell
.\install.ps1
python -m pip install -r requirements.lock
grounded-manual doctor
```

## Create a Project Pack

```bash
grounded-manual init-project /path/to/project
grounded-manual extract-pdf /path/to/manual.pdf --root /path/to/project --source-id manual --sync-policy local
grounded-manual register-source /path/to/source.m --root /path/to/project --source-id source_m --kind code
grounded-manual build-index --root /path/to/project
grounded-manual search --root /path/to/project "installation"
```

See `examples/minimal_project/` for a tiny reproducible pack with relative
fixtures, claims, extracted PDF text, and expected audit output.

For human-friendly prompt recipes, see [ASKING_CODEX.md](ASKING_CODEX.md).
For local AI agents, see [AI_AGENT_QUICKSTART.md](AI_AGENT_QUICKSTART.md).

## Evidence Rules

- Original sources and extracted source spans are evidence.
- `claims/claims.jsonl` records auditable facts.
- `manual/manual.ai.md`, `manual/manual.tex`, and `manual/manual.pdf` are derived outputs.
- `index/search.sqlite` is a local cache and should be rebuilt per platform.

## Audit Boundary

`grounded-manual audit-claims` is a locator audit. It can resolve declared
spans and find candidate evidence, but it does not prove that the evidence
semantically supports a claim.

With `--write`, the command only updates `draft`, `needs_review`, and
`unsupported` claims. It preserves `supported`, `partial`, `contradicted`,
`stale`, and `note` statuses by default. Treat `supported` and related
high-confidence statuses as human or external semantic-review results.

Audit logs include both the locator result and the final claim status:
`audit_result`, `claim_status_before`, `claim_status_after`, and
`write_action`. Hits are tagged as `span_resolved` or `fts_candidate`. The
legacy log field `status` is an alias for `audit_result`, not necessarily the
final claim status after preservation rules are applied.

## Cross-Platform Migration

Clone or copy the project pack, map local-only sources in
`sources/local_overrides.yaml`, verify hashes, and rebuild the index:

```bash
grounded-manual doctor --root /path/to/project/docs/grounded_manual
grounded-manual verify-sources --root /path/to/project --mark-stale
grounded-manual build-index --root /path/to/project
```

When registering a source outside the project pack, the manifest stores only a
`local_override` strategy. The absolute path is written to
`sources/local_overrides.yaml`, which is ignored by Git and should be recreated
per machine.
