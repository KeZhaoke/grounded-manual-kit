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

For human-friendly prompt recipes, see [ASKING_CODEX.md](ASKING_CODEX.md).
For local AI agents, see [AI_AGENT_QUICKSTART.md](AI_AGENT_QUICKSTART.md).

## Evidence Rules

- Original sources and extracted source spans are evidence.
- `claims/claims.jsonl` records auditable facts.
- `manual/manual.ai.md`, `manual/manual.tex`, and `manual/manual.pdf` are derived outputs.
- `index/search.sqlite` is a local cache and should be rebuilt per platform.

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
