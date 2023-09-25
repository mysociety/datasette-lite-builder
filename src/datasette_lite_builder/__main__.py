import click
from .build import build_all, dir_from_theme
from .serve import Rebuilder
from pathlib import Path


@click.group()
def cli():
    pass


@cli.command()
@click.option("--output-dir", default="_site")
@click.option("--theme", default="default")
@click.option("--config-dir", default="")
def build(output_dir: str, theme: str, config_dir: str):

    if config_dir == "":
        config_path = dir_from_theme(theme)
    else:
        config_path = Path(config_dir)

    build_all(Path(output_dir), config_path)


@cli.command()
@click.option("--serve-dir", default="_site")
@click.option("--theme", default="default")
@click.option("--config-dir", default="")
def serve(serve_dir: str, theme: str, config_dir: str):

    if config_dir == "":
        config_path = dir_from_theme(theme)
    else:
        config_path = Path(config_dir)

    Rebuilder(
        port=4000,
        customization_path=config_path,
        serve_path=Path(serve_dir),
        watch_folders=[Path("src"), Path(config_dir)],
    ).run()


if __name__ == "__main__":
    cli()
