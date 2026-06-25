from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audit import SourceValidation, all_audit_summary, count_confidences
from .export_json import hero_slug
from .fandom_client import API_ENDPOINT
from .models import AbilityStats, HeroStats, StatValue


SCHEMA_VERSION = "1.0.0"
DEFAULT_WEB_DATA_DIR = Path("site/public/data/v1")


def build_manifest(hero_count: int, generated_at: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or _utc_now(),
        "source": API_ENDPOINT,
        "hero_count": hero_count,
        "data_files": {
            "hero_index": "heroes.index.json",
            "audit_summary": "audit-summary.json",
            "hero_detail_dir": "heroes/",
        },
    }


def build_hero_index(heroes: list[HeroStats]) -> list[dict[str, Any]]:
    return [build_hero_index_entry(hero) for hero in heroes]


def build_hero_index_entry(hero: HeroStats) -> dict[str, Any]:
    slug = hero_slug(hero.name)
    confidence_counts = count_confidences([hero])
    return {
        "name": hero.name,
        "slug": slug,
        "role": hero.role,
        "sub_role": hero.sub_role,
        "health": hero.health,
        "ability_count": len(hero.abilities),
        "warning_count": sum(len(ability.parse_warnings) for ability in hero.abilities),
        "confidence_counts": {key: confidence_counts[key] for key in ("high", "medium", "low", "unparsed")},
        "detail_path": f"heroes/{slug}.json",
    }


def build_hero_detail(hero: HeroStats) -> dict[str, Any]:
    slug = hero_slug(hero.name)
    return {
        "schema_version": SCHEMA_VERSION,
        "name": hero.name,
        "slug": slug,
        "role": hero.role,
        "sub_role": hero.sub_role,
        "health": hero.health,
        "abilities": [build_ability_detail(ability) for ability in hero.abilities],
        "audit": {
            "warning_count": sum(len(ability.parse_warnings) for ability in hero.abilities),
            "confidence_counts": build_hero_index_entry(hero)["confidence_counts"],
        },
    }


def build_ability_detail(ability: AbilityStats) -> dict[str, Any]:
    return {
        "name": ability.name,
        "slot": ability.slot,
        "type": ability.type,
        "shot_type": ability.shot_type,
        "stats": {
            field: build_stat_detail(field, stat)
            for field, stat in ability.parsed.items()
        },
        "raw": ability.raw,
        "parse_warnings": ability.parse_warnings,
    }


def build_stat_detail(label: str, stat: StatValue) -> dict[str, Any]:
    return {
        "label": label,
        "raw": stat.raw,
        "value": stat.value,
        "min_value": stat.min_value,
        "max_value": stat.max_value,
        "unit": stat.unit,
        "confidence": stat.confidence,
        "warnings": stat.warnings,
    }


def build_audit_summary(
    playable_hero_names: list[str],
    character_rows: list[dict[str, Any]],
    heroes: list[HeroStats],
    ability_rows: list[dict[str, Any]],
    validation: SourceValidation,
) -> dict[str, Any]:
    return all_audit_summary(playable_hero_names, character_rows, heroes, ability_rows, validation)


def write_web_data(
    heroes: list[HeroStats],
    audit_summary: dict[str, Any],
    output_dir: str | Path = DEFAULT_WEB_DATA_DIR,
) -> dict[str, Path]:
    base_dir = Path(output_dir)
    heroes_dir = base_dir / "heroes"
    heroes_dir.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(hero_count=len(heroes))
    hero_index = build_hero_index(heroes)

    paths = {
        "manifest": base_dir / "manifest.json",
        "hero_index": base_dir / "heroes.index.json",
        "audit_summary": base_dir / "audit-summary.json",
    }
    _write_json(paths["manifest"], manifest)
    _write_json(paths["hero_index"], hero_index)
    _write_json(paths["audit_summary"], audit_summary)

    for hero in heroes:
        _write_json(heroes_dir / f"{hero_slug(hero.name)}.json", build_hero_detail(hero))

    return paths


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
