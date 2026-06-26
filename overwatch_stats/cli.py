from __future__ import annotations

import argparse
import difflib
import json
import sys

from .audit import all_audit_summary, build_all_audit, hero_audit_summary, render_all_audit, render_hero_audit
from .export_json import hero_to_json, write_all, write_hero
from .fandom_client import FandomApiError, FandomClient
from .images import DEFAULT_ABILITY_IMAGE_DIR, DEFAULT_HERO_IMAGE_DIR, download_ability_icons, download_hero_portraits
from .normalize import normalize_selected, normalize_hero
from .web_export import DEFAULT_WEB_DATA_DIR, build_audit_summary, write_web_data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Overwatch hero stats from the Overwatch Fandom Cargo API.")
    parser.add_argument("--refresh", action="store_true", help="Bypass local cache and refetch API data.")
    parser.add_argument("--cache-dir", default="data/cache", help="Directory for cached raw API responses.")
    parser.add_argument("--output-dir", default="data/output", help="Directory for exported JSON files.")
    parser.add_argument("--retries", type=int, default=5, help="Number of times to retry temporary Fandom API rate limits.")
    parser.add_argument("--retry-delay", type=float, default=10.0, help="Base seconds to wait between rate-limit retries.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    hero = subparsers.add_parser("hero", help="Fetch, normalize, print, and export one hero.")
    hero.add_argument("name")

    raw = subparsers.add_parser("raw", help="Print raw Cargo rows for one hero.")
    raw.add_argument("name")

    refresh = subparsers.add_parser("refresh", help="Refresh and export one hero.")
    refresh.add_argument("name")

    audit = subparsers.add_parser("audit", help="Print parser/source quality audit without exporting JSON.")
    audit.add_argument("target", help="Hero name or all.")
    audit.add_argument("--json", action="store_true", help="Print a stable JSON audit summary instead of text.")

    web_data = subparsers.add_parser("web-data", help="Generate static website-ready JSON data files.")
    web_data.add_argument("--refresh", action="store_true", dest="command_refresh", help="Bypass local cache and refetch API data.")
    web_data.add_argument("--output-dir", default=str(DEFAULT_WEB_DATA_DIR), help="Directory for generated website data.")

    images = subparsers.add_parser("images", help="Download hero portraits for the static website.")
    images.add_argument("--refresh", action="store_true", dest="command_refresh", help="Redownload existing portrait files.")
    images.add_argument("--output-dir", default=str(DEFAULT_HERO_IMAGE_DIR), help="Directory for generated hero portraits.")

    ability_icons = subparsers.add_parser("ability-icons", help="Download matched ability icons for the static website.")
    ability_icons.add_argument("--refresh", action="store_true", dest="command_refresh", help="Redownload existing ability icon files.")
    ability_icons.add_argument("--output-dir", default=str(DEFAULT_ABILITY_IMAGE_DIR), help="Directory for generated ability icons.")
    ability_icons.add_argument(
        "--heroes-data-dir",
        default=str(DEFAULT_WEB_DATA_DIR / "heroes"),
        help="Directory containing generated hero detail JSON files.",
    )

    subparsers.add_parser("all", help="Fetch and export all heroes.")
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_output()
    args = build_parser().parse_args(argv)
    refresh = args.refresh or args.command == "refresh" or getattr(args, "command_refresh", False)
    client = FandomClient(
        cache_dir=args.cache_dir,
        refresh=refresh,
        max_retries=args.retries,
        retry_delay=args.retry_delay,
    )
    try:
        if args.command in {"hero", "refresh"}:
            return _hero(client, args.name, args.output_dir)
        if args.command == "raw":
            return _raw(client, args.name)
        if args.command == "all":
            return _all(client, args.output_dir)
        if args.command == "audit":
            return _audit(client, args.target, json_output=args.json)
        if args.command == "web-data":
            return _web_data(client, args.output_dir)
        if args.command == "images":
            return _images(
                args.output_dir,
                refresh=refresh,
                cache_dir=args.cache_dir,
                max_retries=args.retries,
                retry_delay=args.retry_delay,
            )
        if args.command == "ability-icons":
            return _ability_icons(
                args.heroes_data_dir,
                args.output_dir,
                refresh=refresh,
                cache_dir=args.cache_dir,
                max_retries=args.retries,
                retry_delay=args.retry_delay,
            )
    except FandomApiError as exc:
        print(f"Fandom API error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Export failed: {exc}", file=sys.stderr)
        return 1
    return 0


def _configure_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _hero(client: FandomClient, name: str, output_dir: str) -> int:
    hero_row = client.get_hero_metadata(name)
    if not hero_row:
        _print_not_found(client, name)
        return 3
    hero = normalize_hero(hero_row, client.get_hero_abilities(hero_row.get("Name", name)))
    write_hero(hero, output_dir=output_dir)
    print(hero_to_json(hero))
    return 0


def _raw(client: FandomClient, name: str) -> int:
    hero_row = client.get_hero_metadata(name)
    if not hero_row:
        _print_not_found(client, name)
        return 3
    payload = {
        "hero": hero_row,
        "abilities": client.get_hero_abilities(hero_row.get("Name", name)),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _all(client: FandomClient, output_dir: str) -> int:
    hero_names = client.get_hero_page_names()
    hero_rows = client.get_all_heroes()
    ability_rows = client.get_all_abilities()
    heroes = normalize_selected(hero_rows, ability_rows, hero_names)
    path = write_all(heroes, output_dir=output_dir)
    print(f"Exported {len(heroes)} heroes to {path}")
    return 0


def _audit(client: FandomClient, target: str, json_output: bool = False) -> int:
    if target.casefold() == "all":
        hero_names = client.get_hero_page_names()
        hero_rows = client.get_all_heroes()
        ability_rows = client.get_all_abilities()
        heroes, validation = build_all_audit(hero_names, hero_rows, ability_rows)
        if json_output:
            print(json.dumps(all_audit_summary(hero_names, hero_rows, heroes, ability_rows, validation), ensure_ascii=False, indent=2))
        else:
            print(render_all_audit(hero_names, hero_rows, heroes, ability_rows, validation))
        return 0

    hero_row = client.get_hero_metadata(target)
    if not hero_row:
        _print_not_found(client, target)
        return 3
    hero_name = hero_row.get("Name", target)
    ability_rows = client.get_hero_abilities(hero_name)
    hero = normalize_hero(hero_row, ability_rows)
    if json_output:
        print(json.dumps(hero_audit_summary(hero, len(ability_rows)), ensure_ascii=False, indent=2))
    else:
        print(render_hero_audit(hero, len(ability_rows)))
    return 0


def _web_data(client: FandomClient, output_dir: str) -> int:
    hero_names = client.get_hero_page_names()
    hero_rows = client.get_all_heroes()
    ability_rows = client.get_all_abilities()
    heroes, validation = build_all_audit(hero_names, hero_rows, ability_rows)
    audit_summary = build_audit_summary(hero_names, hero_rows, heroes, ability_rows, validation)
    paths = write_web_data(heroes, audit_summary, output_dir=output_dir)
    print(f"Generated web data for {len(heroes)} heroes in {paths['manifest'].parent}")
    return 0


def _images(
    output_dir: str,
    refresh: bool = False,
    cache_dir: str = "data/cache",
    max_retries: int = 5,
    retry_delay: float = 10.0,
) -> int:
    result = download_hero_portraits(
        output_dir=output_dir,
        refresh=refresh,
        cache_dir=f"{cache_dir}/images",
        max_retries=max_retries,
        retry_delay=retry_delay,
    )
    print(f"Found {result['category_file_count']} files in hero icon category.")
    print(f"Selected {result['selected_count']} hero portrait files.")
    print(f"Downloaded {result['downloaded_count']} portraits.")
    print(f"Skipped {result['skipped_existing_count']} existing portraits.")
    if result["failed_count"]:
        print(f"Failed {result['failed_count']} portraits:", file=sys.stderr)
        for failure in result["failed"]:
            print(f"- {failure['file_title']}: {failure['error']}", file=sys.stderr)
    print(f"Wrote manifest to {result['manifest_path']}")
    return 1 if result["failed_count"] and not result["entries"] else 0


def _ability_icons(
    heroes_data_dir: str,
    output_dir: str,
    refresh: bool = False,
    cache_dir: str = "data/cache",
    max_retries: int = 5,
    retry_delay: float = 10.0,
) -> int:
    result = download_ability_icons(
        heroes_data_dir=heroes_data_dir,
        output_dir=output_dir,
        refresh=refresh,
        cache_dir=f"{cache_dir}/images",
        max_retries=max_retries,
        retry_delay=retry_delay,
    )
    print(f"Found {result['category_file_count']} files in ability icon categories.")
    print(f"Scanned {result['hero_category_count']} hero ability icon categories.")
    print(f"Needed {result['needed_ability_count']} exported abilities.")
    print(f"Selected {result['selected_count']} matched ability icons.")
    print(f"Downloaded {result['downloaded_count']} ability icons.")
    print(f"Skipped {result['skipped_existing_count']} existing ability icons.")
    print(f"Failed {result['failed_count']} ability icons.")
    if result["failed_count"]:
        print(f"Failed {result['failed_count']} ability icons:", file=sys.stderr)
        for failure in result["failed"]:
            print(f"- {failure['file_title']}: {failure['error']}", file=sys.stderr)
    print(f"Wrote manifest to {result['manifest_path']}")
    coverage = result["coverage_report"]
    print(f"Missing after download: {coverage['missing_after_download_count']}.")
    print(f"Duplicate name collisions: {coverage['duplicate_name_collision_count']}.")
    print(f"Wrote coverage report to {result['coverage_report_path']}")
    return 1 if result["failed_count"] and not result["entries"] else 0


def _print_not_found(client: FandomClient, name: str) -> None:
    try:
        names = [row.get("Name", "") for row in client.get_all_heroes()]
    except Exception:
        names = []
    close = difflib.get_close_matches(name, names, n=5)
    message = f"Hero not found: {name}"
    if close:
        message += f". Did you mean: {', '.join(close)}?"
    print(message, file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
