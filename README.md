# KODC Reproducibility Workflow

This repository provides a script-first workflow for reproducing KODC processing and
Line 208 EOF analysis tables from NIFS OpenAPI data. Raw data, generated CSV files,
and analysis outputs are intentionally excluded from Git so the repository stays
small and reproducible.

## Quick Start

1. Install [Pixi](https://pixi.sh/).
2. Set your NIFS OpenAPI key with either an environment variable:

   ```bash
   export NIFS_API_KEY="your-api-key"
   ```

   Or store it in a local file that is ignored by Git:

   ```bash
   cp NIFS_API_KEY.example NIFS_API_KEY
   # edit NIFS_API_KEY and replace the placeholder with your issued key
   ```

3. Download raw yearly JSON files:

   ```bash
   pixi run download -- --start-year 1961 --end-year 2025
   ```

4. Convert JSON files to CSV:

   ```bash
   pixi run convert
   ```

5. Download station metadata from the `sooCode` endpoint:

   ```bash
   pixi run download-metadata -- --regions E W S EC
   ```

6. Generate the official analysis tables:

   ```bash
   pixi run analyze -- --line 208 --start-date 1982-01-01 --end-date 2025-12-31 --min-observations 240
   ```

7. Generate optional PC lead-lag composite figures:

   ```bash
   pixi run visualize -- --line 208 --lags -2 -4 -6 -12 0 2 4 6 12
   ```

The same default workflow can be run end-to-end with:

```bash
pixi run reproduce
```

## Outputs

The official generated tables are written to `outputs/tables/`:

- `line208_anomalies.csv`
- `all_station_anomalies.csv`
- `station_metadata.csv`
- `line208_pcs.csv`
- `line208_variance.csv`

Optional figures are written to `outputs/figures/`. The visualization command
draws lon-lat triangulated contour maps on a Cartopy `PlateCarree` map, adds
coastlines, uses one fixed map extent across generated figures, masks long
triangle edges to avoid spatial jumps, highlights Line 208 in each map, and
creates PC lead-lag composite maps for the requested month offsets. Station
metadata from `sooCode` is used during preprocessing so interpolation depths do
not exceed each station's reported bottom depth (`bot_dep`).

## Data Provenance

The download step queries the NIFS OpenAPI endpoint with `id=sooList` and yearly
date windows. Station metadata are queried with `id=sooCode` for the region codes
`E`, `W`, `S`, and `EC`. The API key is read from the `NIFS_API_KEY`
environment variable first, then from a local `NIFS_API_KEY` file if present.
Do not commit real API keys, raw JSON files, converted CSV files, or generated
analysis outputs.

## Citation

If you use this workflow, please cite the software packages used for the
reproducible environment and analysis, including Pixi, Python, requests, pandas,
NumPy, SciPy, eofs, pytest, Ruff, and Jupyter Notebook, according to each
package's recommended citation.

## AI Assistance

This repository was refactored and documented with assistance from ChatGPT Codex
(OpenAI).

## Development

Run tests and linting with:

```bash
pixi run test
pixi run lint
```

The package code lives under `src/kodc/`. The legacy notebook logic has been
refactored into reusable modules for download, conversion, preprocessing, and EOF
table generation.

## License

This project is distributed under the MIT License. See `LICENSE` for details.

## 한국어 요약

이 저장소는 KODC 자료 처리와 Line 208 EOF 분석 표 생성을 다른 연구자가
재현할 수 있도록 Pixi 기반 스크립트 워크플로로 정리한 프로젝트입니다.
원자료, 변환된 CSV, 산출물은 Git에 포함하지 않고, `NIFS_API_KEY` 환경변수로
API key를 설정한 뒤 `pixi run download`, `pixi run convert`,
`pixi run analyze` 순서로 실행합니다.
