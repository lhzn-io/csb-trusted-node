"""``csb-node`` command-line entry point."""

from pathlib import Path

import click

from csb_trusted_node import __version__
from csb_trusted_node.config import load_config
from csb_trusted_node.ingest import DEFAULT_MIN_BYTES, ingest_directory
from csb_trusted_node.ledger import SqliteLedgerStore
from csb_trusted_node.metadata import new_unique_vessel_id
from csb_trusted_node.validation import validate_b12


@click.group()
@click.version_option(__version__)
def cli() -> None:
    """Operate an IHO Crowdsourced Bathymetry Trusted Node."""


@cli.command("vessel-id")
@click.option("--prefix", required=True, help="This node's uniqueVesselID prefix.")
def vessel_id(prefix: str) -> None:
    """Allocate a new B-12 uniqueVesselID."""
    click.echo(new_unique_vessel_id(prefix))


@cli.command()
@click.argument("document", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def validate(document: Path) -> None:
    """Validate a B-12 GeoJSON file against CSB schema 3.1.0."""
    result = validate_b12(document)
    if result.valid:
        click.echo(f"OK  {document}")
        return
    click.echo(f"INVALID  {document}", err=True)
    for error in result.errors:
        click.echo(f"  {error}", err=True)
    raise SystemExit(1)


@cli.command()
@click.argument("src", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--config",
    "config_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Node configuration (TOML), kept outside the repository.",
)
@click.option(
    "--out",
    "out_dir",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Output directory.",
)
@click.option(
    "--ledger",
    "ledger_path",
    type=click.Path(dir_okay=False, path_type=Path),
    help="SQLite ledger (default: OUT/ledger.sqlite).",
)
@click.option("--min-bytes", default=DEFAULT_MIN_BYTES, show_default=True, help="Skip smaller files.")
def ingest(src: Path, config_path: Path, out_dir: Path, ledger_path: Path | None, min_bytes: int) -> None:
    """Convert new WIBL files in SRC to B-12 GeoJSON, trimmed around the vessel's home berth."""
    config = load_config(config_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    store = SqliteLedgerStore(ledger_path or out_dir / "ledger.sqlite")
    try:
        outcomes = ingest_directory(src, config, out_dir, store, min_bytes=min_bytes)
    finally:
        store.close()
    for o in outcomes:
        count = f"{o.soundings:>7}" if o.soundings else " " * 7
        click.echo(f"{o.state:<10} {count}  {o.file}  {o.note}".rstrip())
    if any(o.state == "failed" for o in outcomes):
        raise SystemExit(1)
