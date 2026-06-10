# Minimal Grounded Manual Example

This example is a tiny, reproducible evidence pack for checking the trust
boundary workflow.

The source fixtures live inside the pack at
`docs/grounded_manual/sources/fixtures/`, so the manifest uses relative paths
and does not need `sources/local_overrides.yaml`.

Run from this directory:

```bash
python ../../scripts/grounded_manual.py build-index --root .
python ../../scripts/grounded_manual.py search "locator evidence" --root . --json
python ../../scripts/grounded_manual.py audit-claims --root . --write
```

Expected audit shape:

```text
C-001: needs_review - span resolved, semantic support not checked
C-002: needs_review - span resolved, semantic support not checked
C-003: unsupported - no declared span or text-search evidence found
C-004: needs_review - declared spans only named source_id; source-only locator is not a precise span; text search found possible evidence
N-001: skipped_note - note claims are not locator-audited
```

`needs_review` means the locator audit found a precise span or candidate
evidence. It does not mean the claim is semantically supported.

This example intentionally omits local-only and rebuildable files:
`docs/grounded_manual/sources/local_overrides.yaml`,
`docs/grounded_manual/notes/private_notes.local.md`,
`docs/grounded_manual/index/`, and `docs/grounded_manual/logs/`.
