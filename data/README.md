# Data Directory

Generated data are not committed to Git.

- `raw/`: yearly JSON payloads downloaded from the NIFS OpenAPI.
- `interim/`: CSV files converted from the raw JSON payloads, plus normalized
  `sooCode` station metadata in `station_codes.csv`.

Run `pixi run download`, `pixi run convert`, and `pixi run download-metadata`
to populate these directories.
