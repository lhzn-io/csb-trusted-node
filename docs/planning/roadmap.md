# Roadmap

Durable, public roadmap. Day-to-day task tracking lives in the internal agent-lab.

## Phase 0: Foundations (current)

- [x] Package skeleton, `wibl-python` pinned to an exact commit
- [x] B-12 `trustedNode` model checked against CSB schema 3.1.0 (2024-04)
- [x] Submission ledger state machine with per-step hashes
- [x] CI: ruff, mypy and pytest on GitHub Actions (uv)
- [ ] Sphinx docs site skeleton published

## Phase 1: Ingest and conversion

- [x] Ingest WIBL files and record them as `received` with a SHA-256
- [x] Convert through `wibl-python` (time interpolation, then B-12 GeoJSON) to `converted`
- [x] GNSS time repair: re-time fixes whose time disagrees with the logger clock
- [x] Home-berth privacy trim before anything is written to `shareable/`
- [x] Attach `platform` and `processing` blocks (from the node config for now)
- [x] Validate with `csbschema`, then mark `validated` or `rejected` with reasons
- [x] Durable `LedgerStore` backend (SQLite first)
- [ ] Upstream a packet-filter hook to `wibl-python` so the time repair needs no patching

## Phase 2: Vessel and provider registry

- [ ] Vessel and logger registry (sensor offsets, draft, sounder metadata)
- [ ] Agree the node prefix for `uniqueVesselID` allocation with DCDB
- [ ] Data-licence and contributor consent records

## Phase 3: DCDB submission

- [ ] DCDB upload client (provider key from secret storage, never in the repo)
- [ ] Track `submitted` and `accepted`/`rejected` from the DCDB response
- [ ] Retry and backoff policy, and an idempotent resubmission guard

## Phase 4: Operations and Trusted Node application

- [ ] Deployment profile (container image, storage backend choice)
- [ ] Provenance report: everything received, transformed and forwarded for a vessel or period
- [ ] Operator runbook in `docs/src/`
- [ ] Application package for IHO DCDB Trusted Node status

## Upstream WIBL dependencies

PRs on `CCOMJHC/WIBL` that this node benefits from. The `wibl-python` pin
follows upstream `development`; bump it as each one merges.

- [x] [CCOMJHC/WIBL#134](https://github.com/CCOMJHC/WIBL/pull/134): command processor version sync (merged 2026-10-29)
- [x] [CCOMJHC/WIBL#138](https://github.com/CCOMJHC/WIBL/pull/138): v1.3 packet unpacking (merged 2026-10-29)
- [x] [CCOMJHC/WIBL#139](https://github.com/CCOMJHC/WIBL/pull/139): `wibl_to_ascii` lineage (merged 2026-10-29)
- [x] [CCOMJHC/WIBL#140](https://github.com/CCOMJHC/WIBL/pull/140): hydrographic depth-axis plotting (merged 2026-10-29)
- [ ] [CCOMJHC/WIBL#113](https://github.com/CCOMJHC/WIBL/pull/113): WPA3/PMF support (firmware)
- [ ] [CCOMJHC/WIBL#114](https://github.com/CCOMJHC/WIBL/pull/114): station-mode reconnect loop (firmware)
