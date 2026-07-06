# Data Directory

Generated data are not committed to Git.

- `raw/`: yearly JSON payloads downloaded from the NIFS OpenAPI.
- `interim/`: CSV files converted from the raw JSON payloads.

Run `pixi run download` and `pixi run convert` to populate these directories.
