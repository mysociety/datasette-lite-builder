# Datasette Lite Builder

[Datasette-lite](https://github.com/simonw/datasette-lite) is a pyodide wrapper for Datasette that runs it locally in the browser through Javascript.

This is a builder to construct custom versions of Datasette lite. Primarily for a mySociety themed version but it can be used more generally.

## Usage

There are two options on the CLI `build` and `serve`. Both take:

- `output-dir`: Directory to write the output. 
- `config-dir`: Directory of config files for the datasette theme.
- `theme`: Internal config folders - currently 'default' and 'mysoc'. `config-dir` takes priority.

`build` creates a folder with an index.html and webworker.js (+ any required static files).
`serve` does the same, but also creates a local preview server that refreshes on change to either `datasette_lite_builder` or the specified config dir. 

More details through:

```
python -m datasette_lite_builder --help
```

Everything in the config dir will be transferred to the internal filespace (these are packaged in the rendered file). You can include a `templates` folder [as described in the datasette docs](https://docs.datasette.io/en/stable/custom_templates.html). An additional template option `lite_index.html` can override the host template file for adjusting the initial loading screen. 

Anything in the 'static' directory is directly copied across the `output-dir` - use this for images required for a theme. 

### GitHub Action

This repo can also be used as a step in a Github Action. This is meant for injecting a datasette instance as part of a static site that is primarily rendered from a separate framework. 

See the [separate readme](ACTION_README.md) for more details. 

## Changes over base datasette lite

* Restructured the python and javascript into seperate files.
* Template files can be packaged to customise datasette lite.
* Loading page can be customised, by default it will look similar but there are more jinja blocks defines to remove or modify content. 
* Custom version of the `table.js` to work within datasette lite.
* CSS and JS files loaded from within the internal file structure (or datasette itself) will be injected in by javascript (no longer requires the datasette css to be specified in the lite_index).
* If the metadata_url parameter is `datapackage.json`, it will adjust the frictionless datapackage standard to what datasette expects. Additional datasette parameters can be set on the database or table level through adding items to a `datasette`` level under `custom`.