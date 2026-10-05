# csb-trusted-node

Operational backbone for a Crowdsourced Bathymetry (CSB) Trusted Node, following
the IHO B-12 *Guidance to Crowdsourced Bathymetry* and contributing to the IHO
Data Centre for Digital Bathymetry (DCDB).

A Trusted Node sits between volunteer vessels and the DCDB. It keeps a registry
of the vessels and loggers it represents, attaches B-12 metadata to their
soundings, validates each submission against the CSB GeoJSON schema, and keeps
an auditable record of everything it receives and forwards.

This project builds on the [WIBL](https://github.com/CCOMJHC/WIBL) low-cost
logger and its `wibl-python` processing library from the UNH Center for Coastal
and Ocean Mapping / NOAA-UNH Joint Hydrographic Center. WIBL handles decoding and
conversion; this repository handles node operations.

> **Status: candidate node, pre-alpha.** Long Horizon Observatory is not
> currently an IHO DCDB Trusted Node. This is the software we are building to
> operate one, ahead of an application. Nothing here implies IHO or DCDB endorsement.

## What it does today

- `TrustedNodeMetadata`: the B-12 `trustedNode` block, modelled field-for-field on
  CSB schema 3.1.0 (2024-04) as shipped in [`csbschema`](https://pypi.org/project/csbschema/).
- `csb-node vessel-id`: allocates `uniqueVesselID`s under this node's prefix.
- `csb-node validate`: checks a B-12 GeoJSON file against the schema.
- A submission ledger (`received` → `converted` → `validated` → `submitted` →
  `accepted`) that records a timestamp and content hash at every step.

## Install

Dependencies are managed with [uv](https://docs.astral.sh/uv/). `uv.lock` pins
everything, including the exact `wibl-python` commit.

```bash
uv sync --extra dev
uv run pytest
uv run csb-node --help
```

Plain pip works too, without the lockfile's exact pins:

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"   # Windows: .venv\Scripts\pip
pytest
```

WIBL's map rendering (`wibl.visualization`) needs the GMT C library installed on
the host. The node's ingest and validation path doesn't use it.

## Documentation

User and operator documentation lives in [`docs/src/`](docs/src/). The roadmap is
in [`docs/planning/roadmap.md`](docs/planning/roadmap.md).

## License

MIT. See [LICENSE](LICENSE).
