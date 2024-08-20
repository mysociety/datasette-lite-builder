from typing import Optional, Tuple, NamedTuple

# https://github.com/pyodide/pyodide/issues/3880#issuecomment-1560130092
import os
import re
from pathlib import Path

os.link = os.symlink

cached_css = {}
cached_js = {}


class MiniResponse(NamedTuple):
    response_code: int
    content_type: str
    text: str


async def get_lite_response(ds, web_path: str) -> MiniResponse:
    potential_local_file = Path(web_path[1:])
    # seperate responses for css, js, and html
    if potential_local_file.suffix == ".css" and potential_local_file.exists():
        print("returning custom css")
        response_code, content_type, text = [
            200,
            "text/css",
            potential_local_file.read_text(),
        ]
    elif potential_local_file.suffix == ".js" and potential_local_file.exists():
        print("returning custom js")
        response_code, content_type, text = [
            200,
            "application/javascript",
            potential_local_file.read_text(),
        ]
    else:
        # just get it normally from datasette
        response = await ds.client.get(web_path, follow_redirects=True)
        response_code, content_type, text = [
            response.status_code,
            response.headers.get("content-type"),
            response.text,
        ]

    final_lines = []
    for line in text.splitlines():
        # if the line contains a link to a CSS file, grab that css file and add it as an inline stylesheet
        if 'rel="stylesheet"' in line:
            css_url = re.search(r'href="([^"]+)"', line).group(1)
            if css_url.startswith("/"):
                css_response = cached_css.get(
                    css_url, await get_lite_response(ds, css_url)
                )
                final_lines.append(f"<style>{css_response.text}</style>")
            else:
                final_lines.append(line)
        # if importing a JS file, a script with an src line, grab that JS file and add it as an inline script
        elif 'src="' in line and "<script" in line:
            js_url = re.search(r'src="([^"]+)"', line).group(1)
            if js_url.startswith("/-/") and "table.js" in js_url:
                print(js_url)
                js_response = cached_js.get(js_url, await get_lite_response(ds, js_url))
                final_lines.append(
                    f'<script class="injected">{js_response.text}</script>'
                )
        elif "<script>" in line:
            # tag all inline scripts as injected so they can be run in a sec
            final_lines.append(line.replace("<script>", '<script class="injected">'))
        else:
            final_lines.append(line)

    text = "\\n".join(final_lines)

    return MiniResponse(response_code, content_type, text)


def datapackage_to_metadata(datapackage: dict) -> dict:
    """
    Convert a frictionless datapackage to datasette metadata
    """

    metadata = {
        "title": datapackage.get("title"),
        "description": datapackage.get("description"),
    }

    for licence in datapackage.get("licenses", []):
        metadata["license"] = licence["name"]
        metadata["license_url"] = licence["path"]
        break

    def resource_to_table(resource: dict) -> Tuple[str, dict]:
        resource_name = resource["name"]
        description_html = resource.get("description", "")
        columns = {
            column["name"]: column["description"]
            for column in resource["schema"]["fields"]
        }
        custom_table = resource.get("custom", {}).get("datasette", {})
        table_data = {
            "title": resource["title"],
            "description_html": description_html,
            "columns": columns,
        }
        if "dataset_order" in resource.get("custom", {}):
            table_data["dataset_order"] = resource["custom"]["dataset_order"]
        table_data.update(custom_table)
        return resource_name, table_data

    database = {
        "title": datapackage.get("title"),
        "description_html": datapackage.get("description"),
        "tables": dict(
            resource_to_table(resource) for resource in datapackage["resources"]
        ),
    }

    database_level_custom = datapackage.get("custom", {}).get("datasette", {})
    database.update(database_level_custom)

    metadata["databases"] = {datapackage["name"]: database}

    return metadata


async def load_datasette(
    install_urls: list[str],
    default_metadata: dict[str, str],
    metadata_url: Optional[str],
    sources: list[Tuple[str, str]],
    memory_setting: bool,
    data_to_load: list[Tuple[str, str]],
    config_static: dict[str, str],
):
    # split up file sources
    # get source url for first sql if present, otherwise empty list
    sqls = next((source[1] for source in sources if source[0] == "sql"), [])

    # limit to file sources
    file_sources = [
        source for source in sources if source[0] in ["csv", "json", "parquet"]
    ]

    # Grab that fixtures.db database

    # write templates to internal filespace
    import html

    for file_path, contents in config_static.items():
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w") as fp:
            print(f"Writing custom file {p}")
            fp.write(html.unescape(contents))

    import sqlite3
    from pyodide.http import pyfetch

    names = []
    for name, url in data_to_load:
        if url:
            response = await pyfetch(url)
            with open(name, "wb") as fp:
                fp.write(await response.bytes())
        else:
            sqlite3.connect(name).execute("vacuum")
        names.append(name)

    import micropip

    # Workaround for Requested 'h11<0.13,>=0.11', but h11==0.13.0 is already installed
    await micropip.install("h11==0.12.0")
    await micropip.install("httpx==0.23")
    await micropip.install("datasette")
    # Install any extra ?install= dependencies

    if install_urls:
        for install_url in install_urls:
            await micropip.install(install_url)
    # Execute any ?sql=URL SQL

    if sqls:
        for sql_url in sqls:
            # Fetch that SQL and execute it
            response = await pyfetch(sql_url)
            sql = await response.string()
            sqlite3.connect("data.db").executescript(sql)

    metadata = {}
    metadata.update(default_metadata)

    if metadata_url:
        response = await pyfetch(metadata_url)
        content = await response.string()

        if metadata_url.endswith("datapackage.json"):
            import json

            content = json.loads(content)
            metadata.update(datapackage_to_metadata(content))
        else:
            from datasette.utils import parse_metadata

            metadata.update(parse_metadata(content))

    # Import data from ?csv=URL CSV files/?json=URL JSON files

    if file_sources:
        await micropip.install("sqlite-utils==3.28")
        import sqlite_utils, json
        from sqlite_utils.utils import rows_from_file, TypeTracker, Format

        db = sqlite_utils.Database("data.db")
        table_names = set()
        for source_type, urls in file_sources:
            for url in urls:
                # Derive table name from URL
                bit = url.split("/")[-1].split(".")[0].split("?")[0]
                bit = bit.strip()
                if not bit:
                    bit = "table"
                prefix = 0
                base_bit = bit
                while bit in table_names:
                    prefix += 1
                    bit = "{}_{}".format(base_bit, prefix)
                table_names.add(bit)

                if source_type == "csv":
                    tracker = TypeTracker()
                    response = await pyfetch(url)
                    with open("csv.csv", "wb") as fp:
                        fp.write(await response.bytes())
                    db[bit].insert_all(
                        tracker.wrap(
                            rows_from_file(open("csv.csv", "rb"), Format.CSV)[0]
                        )
                    )
                    db[bit].transform(types=tracker.types)
                elif source_type == "json":
                    pk = None
                    response = await pyfetch(url)
                    with open("json.json", "wb") as fp:
                        json_bytes = await response.bytes()
                        try:
                            json_data = json.loads(json_bytes)
                        except json.decoder.JSONDecodeError:
                            # Maybe it's newline-delimited JSON?
                            # This will raise an unhandled exception if not
                            json_data = [
                                json.loads(line) for line in json_bytes.splitlines()
                            ]
                    if isinstance(json_data, dict) and all(
                        isinstance(v, dict) for v in json_data.values()
                    ):
                        fixed = []
                        pk = "_key"
                        for key, value in json_data.items():
                            value["_key"] = key
                            fixed.append(value)
                        json_data = fixed
                    elif isinstance(json_data, dict) and any(
                        isinstance(v, list) for v in json_data.values()
                    ):
                        for key, value in json_data.items():
                            if (
                                isinstance(value, list)
                                and value
                                and isinstance(value[0], dict)
                            ):
                                json_data = value
                                break
                    assert isinstance(
                        json_data, list
                    ), "JSON data must be a list of objects"
                    db[bit].insert_all(json_data, pk=pk)
                elif source_type == "parquet":
                    await micropip.install("fastparquet")
                    import fastparquet

                    response = await pyfetch(url)
                    with open("parquet.parquet", "wb") as fp:
                        fp.write(await response.bytes())
                    df = fastparquet.ParquetFile("parquet.parquet").to_pandas()
                    df.to_sql(bit, db.conn, if_exists="replace")
    from datasette.app import Datasette

    ds = Datasette(
        names,
        settings={
            "num_sql_threads": 0,
        },
        metadata=metadata,
        template_dir="templates",
        memory=memory_setting,
    )
    await ds.invoke_startup()
    return ds
