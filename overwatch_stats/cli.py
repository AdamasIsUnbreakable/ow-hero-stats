from __future__ import annotations

import argparse
import difflib
import json
import sys

from .export_json import hero_to_json, write_all, write_hero
from .fandom_client import FandomApiError, FandomClient
from .normalize import normalize_selected, normalize_hero


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

    subparsers.add_parser("all", help="Fetch and export all heroes.")
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_output()
    args = build_parser().parse_args(argv)
    refresh = args.refresh or args.command == "refresh"
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
