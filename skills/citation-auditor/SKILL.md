---
name: citation-auditor
description: Use when independently auditing source-grounded manual claims, checking whether claims in claims.jsonl are supported by primary sources or extracted evidence, detecting stale/weak/unsupported citations, and ensuring derived manuals do not self-prove their facts.
metadata:
  short-description: Independently audit grounded manual claims
---

# Citation Auditor

Use this skill when the user asks to audit, verify, review, or challenge the
citations and claims in a `docs/grounded_manual/` evidence pack.

## Hard Boundary

`manual/manual.ai.md`, `manual/manual.tex`, and `manual/manual.pdf` are audit
subjects, not evidence. Do not use them to prove claims.

Allowed evidence:

- Original registered sources in `sources/sources.manifest.jsonl`.
- Extracted evidence in `extracted/public/**` and `extracted/local/**`.
- Source-code spans with line numbers.
- Public/private notes, but only as notes and never as primary facts.
- Source/chunk/span hashes and manifests.

## Audit Workflow

1. Run `grounded-manual doctor` and `grounded-manual build-index` if needed.
2. Read `claims/claims.jsonl`.
3. For each claim, resolve declared source spans first.
4. If declared spans fail, search evidence for possible support.
5. Assign one status:
   - `supported`: declared evidence supports the claim.
   - `partial`: evidence supports only part of the claim.
   - `unsupported`: no indexed evidence supports it.
   - `contradicted`: indexed evidence conflicts with it.
   - `stale`: source hash or span hash changed.
   - `needs_review`: possible evidence exists but needs human review.
   - `note`: claim is explicitly personal note/interpretation.
6. Record query terms, hits, status, and reason in logs.

Preferred command:

```bash
grounded-manual audit-claims
```

Use `--write` only when the user wants claim statuses updated.

## Reporting

Lead with findings. For each issue include:

```text
Claim: C-001
Status: unsupported
Problem: Declared PDF page does not contain the claim.
Evidence checked: source.pdf p.12, chunk hash ...
Suggested fix: Narrow claim or add correct source span.
```

Do not soften missing citations. If the evidence is not there, say so.

