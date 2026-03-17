import sys
from pathlib import Path

import click

from .config import load_config
from .ffmpeg_ops import render_project
from .pipeline import build_pipeline, describe_pipeline
from .project import scan_project, scan_projects_folder


@click.group()
def cli() -> None:
    """FullControl MTG – automated video editor powered by ffmpeg."""


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _render_single(project, config, output: Path | None, dry_run: bool) -> None:
    segments = build_pipeline(project, config)

    click.echo(f"Project  : {project.name}")
    click.echo(f"Deck tech: {project.deck_tech.name}")
    click.echo(f"Games    : {project.num_games}")
    click.echo(f"Pipeline : {describe_pipeline(segments)}")

    if dry_run:
        return

    if output is None:
        config.output_folder.mkdir(parents=True, exist_ok=True)
        output = config.output_folder / f"{project.name}.mp4"

    click.echo(f"Rendering → {output}")
    render_project(segments, output, config)
    click.echo("Done.")


# ---------------------------------------------------------------------------
# run  – default entry point, driven by PROCESS_MULTI
# ---------------------------------------------------------------------------

@cli.command("run")
@click.option("--dry-run", is_flag=True, help="Print pipeline order(s) without rendering.")
def run_cmd(dry_run: bool) -> None:
    """Process projects using PROJECT_FOLDER_PATH and PROCESS_MULTI from .env.

    \b
    PROCESS_MULTI=false  →  PROJECT_FOLDER_PATH is the single project folder
                             (e.g. ./input/2026.03.13-deck-name)
    PROCESS_MULTI=true   →  PROJECT_FOLDER_PATH is the parent folder whose
                             subfolders are all project folders
                             (e.g. ./input/ containing 2026.03.13-* dirs)
    """
    config = load_config()
    path = config.project_folder_path

    if not path.exists():
        click.echo(f"Error: PROJECT_FOLDER_PATH not found: {path}", err=True)
        sys.exit(1)

    if not config.process_multi:
        try:
            project = scan_project(path)
        except ValueError as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)
        _render_single(project, config, output=None, dry_run=dry_run)

    else:
        projects = scan_projects_folder(path)
        if not projects:
            click.echo(f"No video-containing subfolders found in {path}.")
            return

        click.echo(f"Found {len(projects)} project(s) in {path}\n")
        config.output_folder.mkdir(parents=True, exist_ok=True)

        for i, project in enumerate(projects, 1):
            click.echo(f"[{i}/{len(projects)}]")
            try:
                _render_single(project, config, output=None, dry_run=dry_run)
            except Exception as exc:
                click.echo(f"  ERROR: {exc}", err=True)
            click.echo()


# ---------------------------------------------------------------------------
# process  – explicit single project folder
# ---------------------------------------------------------------------------

@cli.command("process")
@click.argument("folder", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path. Defaults to <OUTPUT_FOLDER>/<project-name>.mp4",
)
@click.option("--dry-run", is_flag=True, help="Print the pipeline order without rendering.")
def process_cmd(folder: Path, output: Path | None, dry_run: bool) -> None:
    """Process a single project FOLDER directly."""
    config = load_config()

    try:
        project = scan_project(folder)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    _render_single(project, config, output, dry_run)


# ---------------------------------------------------------------------------
# batch  – explicit multi-project root folder
# ---------------------------------------------------------------------------

@cli.command("batch")
@click.argument("folder", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--dry-run", is_flag=True, help="Print pipeline orders without rendering.")
def batch_cmd(folder: Path, dry_run: bool) -> None:
    """Process all project subfolders inside FOLDER."""
    config = load_config()

    projects = scan_projects_folder(folder)
    if not projects:
        click.echo(f"No video-containing subfolders found in {folder}.")
        return

    click.echo(f"Found {len(projects)} project(s) in {folder}\n")
    config.output_folder.mkdir(parents=True, exist_ok=True)

    for i, project in enumerate(projects, 1):
        click.echo(f"[{i}/{len(projects)}]")
        try:
            _render_single(project, config, output=None, dry_run=dry_run)
        except Exception as exc:
            click.echo(f"  ERROR: {exc}", err=True)
        click.echo()
