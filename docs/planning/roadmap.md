# Roadmap

Durable, public roadmap. Day-to-day task tracking lives in the internal agent-lab.

## Phase 0: Foundations (current)

- [x] Package skeleton, `wibl-python` pinned to an exact commit
- [x] B-12 `trustedNode` model checked against CSB schema 3.1.0 (2024-04)
- [x] Submission ledger state machine with per-step hashes
- [ ] CI: ruff, mypy and pytest on GitHub Actions (uv)
- [ ] Sphinx docs site skeleton published

## Phase 1: Ingest and conversion

- [ ] Ingest WIBL files and record them as `received` with a SHA-256
- [ ] Convert through `wibl-python` (time interpolation, then B-12 GeoJSON) to `converted`
- [ ] Attach `platform` and `processing` blocks from the vessel registry
- [ ] Validate with `csbschema`, then mark `validated` or `rejected` with reasons
- [ ] Durable `LedgerStore` backend (SQLite first)

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

Open PRs on `CCOMJHC/WIBL` that this node benefits from. Bump the `wibl-python`
pin once they merge.

- [CCOMJHC/WIBL#134](https://github.com/CCOMJHC/WIBL/pull/134): command processor version sync
- [CCOMJHC/WIBL#138](https://github.com/CCOMJHC/WIBL/pull/138): v1.3 packet unpacking
- [CCOMJHC/WIBL#139](https://github.com/CCOMJHC/WIBL/pull/139): `wibl_to_ascii` lineage
- [CCOMJHC/WIBL#140](https://github.com/CCOMJHC/WIBL/pull/140): hydrographic depth-axis plotting
- [CCOMJHC/WIBL#113](https://github.com/CCOMJHC/WIBL/pull/113): WPA3/PMF support
- [CCOMJHC/WIBL#114](https://github.com/CCOMJHC/WIBL/pull/114): station-mode reconnect loop
