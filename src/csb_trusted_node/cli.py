"""``csb-node`` command-line entry point."""

from pathlib import Path

import click

from csb_trusted_node import __version__
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
