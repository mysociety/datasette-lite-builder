# Render Datasette Lite

Render datasette lite from template folder or theme.
If given, config_dir preferred to theme.

## Usage

```yaml

# It is better practice to use the SHA hash of this tag rather than the tag itself.
- uses: mysociety/datasette-lite-builder@v0
  id: example-step 
  with:
    theme: 'default'  # default
    publish_dir: 'docs'  # default
    config_dir: '' 

```

## Inputs

### theme

Inbuilt theme

Default: default

### publish_dir

Directory in repo to publish to.

Default: docs

### config_dir

Directory in repo to take config from.

