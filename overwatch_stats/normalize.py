from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .models import AbilityStats, HeroStats, StatValue
from .parse_stats import PARSERS, clean_text


API_ENDPOINT = "https://overwatch.fandom.com/api.php"
ROLE_OVERRIDES = {
    "shion": "Damage",
}


def normalize_hero(hero_row: dict[str, Any], ability_rows: list[dict[str, Any]]) -> HeroStats:
    hero_data = _canonicalize_keys(hero_row)
    name = clean_text(hero_data.get("name")) or "Unknown"
    role = clean_text(hero_data.get("role")) or ROLE_OVERRIDES.get(name.casefold())
    hero = HeroStats(
        name=name,
        role=role,
        sub_role=clean_text(hero_data.get("subrole") or hero_data.get("sub_role")),
        health={
            "health": _parse_int(hero_data.get("health")),
            "armor": _parse_int(hero_data.get("armor")),
            "shield": _parse_int(hero_data.get("shield")),
        },
        abilities=[normalize_ability(row) for row in ability_rows],
        source=API_ENDPOINT,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
    return hero


def normalize_all(hero_rows: list[dict[str, Any]], ability_rows: list[dict[str, Any]]) -> list[HeroStats]:
    abilities_by_hero: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ability_rows:
        ability_data = _canonicalize_keys(row)
        hero_name = clean_text(ability_data.get("hero_name")) or ""
        abilities_by_hero[hero_name.casefold()].append(row)
    return [
        normalize_hero(row, abilities_by_hero.get((clean_text(_canonicalize_keys(row).get("name")) or "").casefold(), []))
        for row in hero_rows
    ]


def normalize_selected(
    hero_rows: list[dict[str, Any]],
    ability_rows: list[dict[str, Any]],
    hero_names: list[str],
) -> list[HeroStats]:
    wanted = {name.casefold() for name in hero_names}
    abilities_by_hero: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ability_rows:
        ability_data = _canonicalize_keys(row)
        hero_name = clean_text(ability_data.get("hero_name")) or ""
        if hero_name.casefold() in wanted:
            abilities_by_hero[hero_name.casefold()].append(row)

    rows_by_name = {
        (clean_text(_canonicalize_keys(row).get("name")) or "").casefold(): row
        for row in hero_rows
    }
    heroes: list[HeroStats] = []
    for name in hero_names:
        key = name.casefold()
        hero_row = rows_by_name.get(key) or {"Name": name}
        heroes.append(normalize_hero(hero_row, abilities_by_hero.get(key, [])))
    return heroes


def normalize_ability(row: dict[str, Any]) -> AbilityStats:
    ability_data = _canonicalize_keys(row)
    parsed: dict[str, StatValue] = {}
    warnings: list[str] = []
    for field, parser in PARSERS.items():
        if field not in ability_data:
            continue
        stat = parser(ability_data.get(field))
        parsed[field] = stat
        warnings.extend(f"{field}: {warning}" for warning in stat.warnings)

    return AbilityStats(
        name=clean_text(ability_data.get("ability_name")) or clean_text(ability_data.get("name")) or "Unknown",
        slot=clean_text(ability_data.get("ability_key")),
        type=clean_text(ability_data.get("ability_type")),
        shot_type=_split_list(ability_data.get("shot_type")),
        raw=dict(row),
        parsed=parsed,
        parse_warnings=warnings,
    )


def _parse_int(value: object) -> int | None:
    text = clean_text(value)
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None


def _split_list(value: object) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]


def _canonicalize_keys(row: dict[str, Any]) -> dict[str, Any]:
    canonical: dict[str, Any] = {}
    for key, value in row.items():
        normalized = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(key))
        while "__" in normalized:
            normalized = normalized.replace("__", "_")
        canonical[normalized.strip("_")] = value
    return canonical
