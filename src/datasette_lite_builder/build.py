import jinja2
from pathlib import Path
import json
import shutil

template_path = Path(__file__).parent / "jinja_templates"
lite_config_path = Path(__file__).parent / "lite_config"


def dir_from_theme(theme: str) -> Path:
    """
    themes live in the datasette_lite_builder dir, under themes
    """
    current_dir = Path(__file__).parent
    theme_dir = current_dir / "themes" / theme
    if not theme_dir.exists():
        raise ValueError(f"Theme {theme} not found in {theme_dir}")
    return theme_dir


def build_webworker(dest_path: Path):
    webworker_template = template_path / "webworker.js"
    template = jinja2.Template(webworker_template.read_text())

    context = {}
    context["web_worker_py"] = (template_path / "webworker.py").read_text()

    result = template.render(context)
    (dest_path / "webworker.js").write_text(result)


def get_template_folder(
    template_path: Path, ignore_static: bool = False
) -> dict[str, str]:
    """
    iteratively, for all files in template_path, create a dictionary of path to contents
    """
    result = {}
    static_dir = template_path / "static"
    for path in template_path.glob("**/*"):
        if "static" in path.parts and ignore_static:
            continue

        if path.is_file():
            result[str(path.relative_to(template_path))] = path.read_text()
    return result


def build_index(dest_path: Path, customisation_path: Path):
    custom_templates = customisation_path / "templates"
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader([str(template_path), str(custom_templates)])
    )

    # if there is an lite_index.html in the customisation folder, use that,
    # otherwise 'base_lite_index.html'

    if (custom_templates / "lite_index.html").exists():
        index_template = env.get_template("lite_index.html")
    else:
        index_template = env.get_template("base_lite_index.html")

    lite_config = get_template_folder(lite_config_path)
    custom_files = get_template_folder(customisation_path, ignore_static=True)
    files_to_transfer = {**lite_config, **custom_files}
    context = {
        "config_static": files_to_transfer,
    }

    result = index_template.render(context)
    (dest_path / "index.html").write_text(result)

    # copy static files
    static_dir = customisation_path / "static"
    if static_dir.exists():
        shutil.copytree(static_dir, dest_path / "static", dirs_exist_ok=True)


def build_all(dest_path: Path, customisation_path: Path):
    dest_path.mkdir(exist_ok=True)
    build_webworker(dest_path)
    build_index(dest_path, customisation_path)
