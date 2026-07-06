"""Command-line interface for the KODC reproducibility workflow."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from .analysis import write_analysis_tables
from .config import (
    DEFAULT_BASELINE_END,
    DEFAULT_BASELINE_START,
    DEFAULT_END_DATE,
    DEFAULT_END_YEAR,
    DEFAULT_EOF_MODES,
    DEFAULT_LEAD_LAG_MONTHS,
    DEFAULT_LINE,
    DEFAULT_MIN_OBSERVATIONS,
    DEFAULT_START_DATE,
    DEFAULT_START_YEAR,
    INTERIM_DATA_DIR,
    OUTPUT_FIGURE_DIR,
    OUTPUT_TABLE_DIR,
    RAW_DATA_DIR,
    get_api_key,
)
from .convert import convert_json_directory
from .download import download_years


def _year_range(start_year: int, end_year: int) -> range:
    if end_year < start_year:
        raise argparse.ArgumentTypeError("--end-year must be greater than or equal to --start-year")
    return range(start_year, end_year + 1)


def run_download(args: argparse.Namespace) -> int:
    results = download_years(
        api_key=get_api_key(),
        years=_year_range(args.start_year, args.end_year),
        output_dir=args.output_dir,
        overwrite=args.overwrite,
        timeout=args.timeout,
    )
    for result in results:
        status = "skipped" if result.skipped else "downloaded"
        print(f"{status}: {result.path}")
    return 0


def run_convert(args: argparse.Namespace) -> int:
    paths = convert_json_directory(input_dir=args.input_dir, output_dir=args.output_dir)
    for path in paths:
        print(f"converted: {path}")
    return 0


def run_analyze(args: argparse.Namespace) -> int:
    outputs = write_analysis_tables(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        line=args.line,
        start_date=args.start_date,
        end_date=args.end_date,
        baseline_start=args.baseline_start,
        baseline_end=args.baseline_end,
        min_observations=args.min_observations,
        n_modes=args.modes,
    )
    for name, path in outputs.paths.items():
        print(f"{name}: {path}")
    return 0


def run_visualize(args: argparse.Namespace) -> int:
    from .visualize import write_visualizations

    outputs = write_visualizations(
        table_dir=args.table_dir,
        output_dir=args.output_dir,
        line=args.line,
        modes=args.modes,
        depths=args.depths,
        lag_months=args.lags,
        threshold=args.threshold,
        max_edge_km=args.max_edge_km,
    )
    for path in outputs.paths:
        print(f"figure: {path}")
    for skipped in outputs.skipped:
        print(f"skipped: {skipped}")
    return 0


def run_reproduce(args: argparse.Namespace) -> int:
    download_years(
        api_key=get_api_key(),
        years=_year_range(args.start_year, args.end_year),
        output_dir=args.raw_dir,
        overwrite=args.overwrite,
        timeout=args.timeout,
    )
    convert_json_directory(input_dir=args.raw_dir, output_dir=args.interim_dir)
    outputs = write_analysis_tables(
        input_dir=args.interim_dir,
        output_dir=args.output_dir,
        line=args.line,
        start_date=args.start_date,
        end_date=args.end_date,
        baseline_start=args.baseline_start,
        baseline_end=args.baseline_end,
        min_observations=args.min_observations,
        n_modes=args.modes,
    )
    for name, path in outputs.paths.items():
        print(f"{name}: {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reproducible KODC processing pipeline.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download", help="Download yearly KODC JSON files.")
    download.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    download.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    download.add_argument("--output-dir", type=Path, default=RAW_DATA_DIR)
    download.add_argument("--overwrite", action="store_true")
    download.add_argument("--timeout", type=float, default=60.0)
    download.set_defaults(func=run_download)

    convert = subparsers.add_parser("convert", help="Convert raw JSON files to CSV.")
    convert.add_argument("--input-dir", type=Path, default=RAW_DATA_DIR)
    convert.add_argument("--output-dir", type=Path, default=INTERIM_DATA_DIR)
    convert.set_defaults(func=run_convert)

    analyze = subparsers.add_parser("analyze", help="Generate official EOF analysis tables.")
    add_analysis_arguments(analyze, input_arg="--input-dir")
    analyze.set_defaults(func=run_analyze)

    visualize = subparsers.add_parser("visualize", help="Generate PC lead-lag composite figures.")
    visualize.add_argument("--table-dir", type=Path, default=OUTPUT_TABLE_DIR)
    visualize.add_argument("--output-dir", type=Path, default=OUTPUT_FIGURE_DIR)
    visualize.add_argument("--line", type=int, default=DEFAULT_LINE)
    visualize.add_argument("--modes", type=int, nargs="+", default=None)
    visualize.add_argument("--depths", type=int, nargs="+", default=None)
    visualize.add_argument("--lags", type=int, nargs="+", default=DEFAULT_LEAD_LAG_MONTHS)
    visualize.add_argument("--threshold", type=float, default=1.0)
    visualize.add_argument("--max-edge-km", type=float, default=None)
    visualize.set_defaults(func=run_visualize)

    reproduce = subparsers.add_parser("reproduce", help="Run download, convert, and analyze.")
    reproduce.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    reproduce.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    reproduce.add_argument("--raw-dir", type=Path, default=RAW_DATA_DIR)
    reproduce.add_argument("--interim-dir", type=Path, default=INTERIM_DATA_DIR)
    reproduce.add_argument("--overwrite", action="store_true")
    reproduce.add_argument("--timeout", type=float, default=60.0)
    add_analysis_arguments(reproduce, input_arg=None)
    reproduce.set_defaults(func=run_reproduce)
    return parser


def add_analysis_arguments(parser: argparse.ArgumentParser, *, input_arg: str | None) -> None:
    if input_arg:
        parser.add_argument(input_arg, type=Path, default=INTERIM_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_TABLE_DIR)
    parser.add_argument("--line", type=int, default=DEFAULT_LINE)
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=DEFAULT_END_DATE)
    parser.add_argument("--baseline-start", default=DEFAULT_BASELINE_START)
    parser.add_argument("--baseline-end", default=DEFAULT_BASELINE_END)
    parser.add_argument("--min-observations", type=int, default=DEFAULT_MIN_OBSERVATIONS)
    parser.add_argument("--modes", type=int, default=DEFAULT_EOF_MODES)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
