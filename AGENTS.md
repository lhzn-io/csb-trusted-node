# AGENTS.md: csb-trusted-node

Repo-specific context for AI developer agents. Global fleet rules live in
`$HOME/.agents/global-rules.md`.

## Purpose

The operational code for Long Horizon Observatory's IHO Crowdsourced Bathymetry
Trusted Node: vessel registry, B-12 metadata, validation, submission ledger and
provenance. WIBL decoding and conversion come from `wibl-python` as a dependency.
Do not vendor or fork WIBL code into this repo. Upstream fixes go to
`dfry-lhzn/WIBL` as PRs against `CCOMJHC/WIBL`.

## Planning ledger (public repo)

- `docs/planning/roadmap.md` is the only planning file kept here.
- `task.md`, `implementation_plan.md` and `walkthrough.md` live in the internal
  repo `lhzn-io/unh-ccom-agent-lab` under `docs/planning/csb-trusted-node/`
  (sibling checkout: `../unh-ccom-agent-lab`). They are gitignored here; never
  force-add them.
- This repo is public. Keep fleet hostnames, IPs, credentials, DCDB provider keys
  and vessel owner contact details out of it.

## Layout

| Path | Role |
| :--- | :--- |
| `src/csb_trusted_node/metadata.py` | B-12 `trustedNode` model and `uniqueVesselID` allocation |
| `src/csb_trusted_node/validation.py` | The single entry point to `csbschema` |
| `src/csb_trusted_node/ledger.py` | Submission state machine, history and the `LedgerStore` protocol |
| `src/csb_trusted_node/cli.py` | `csb-node` CLI (click) |
| `docs/src/` | Sphinx (MyST) user and operator docs |

## Schema authority

The B-12 field names, enums and patterns come from `csbschema`'s
`CSB-schema-3_1_0-2024-04.json`. Don't type B-12 fields from memory: read the
schema in the installed `csbschema` package, and keep
`tests/test_metadata.py::test_emitted_document_passes_csbschema` passing.

## Commands

- Environment: uv only (no conda/micromamba). `uv sync --extra dev`; add or bump
  dependencies with `uv add` so `uv.lock` stays authoritative. In OneDrive
  checkouts, set `UV_PROJECT_ENVIRONMENT` to a non-synced path so `.venv` is not synced.
- Tests: `uv run pytest`
- Lint, format and types: `uv run pre-commit run --all-files` (ruff 0.16.9, mypy strict)
- Don't import `wibl.visualization` (it needs GMT) or `wibl.command` (it needs
  `wibl_manager`) from core modules.

## Conventions

- Python 3.12+, strict typing, `pathlib.Path`, lines of 110 characters or fewer.
- Deployment target is undecided. Keep the core portable: storage and queues go
  behind protocols (see `LedgerStore`), with no cloud SDK imports in core modules.
- Git: conventional commits, no emoji, stage files explicitly, and get user review
  before every commit and push (see the global rules).
