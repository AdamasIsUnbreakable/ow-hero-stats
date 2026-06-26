from __future__ import annotations

from collections import Counter
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audit import SourceValidation, all_audit_summary, count_confidences
from .audit import warnings_by_ability
from .export_json import hero_slug
from .fandom_client import API_ENDPOINT
from .models import AbilityStats, HeroStats, StatValue


SCHEMA_VERSION = "1.2.0"
DEFAULT_WEB_DATA_DIR = Path("site/public/data/v1")
STAT_LABELS = {
    "damage": "Damage",
    "damage_falloff_range": "Damage Falloff Range",
    "headshot": "Headshot",
    "headshot_mod": "Headshot Multiplier",
    "heal": "Healing",
    "cooldown": "Cooldown",
    "charges": "Charges",
    "fire_rate": "Fire Rate",
    "ammo": "Ammo",
    "reload_time": "Reload Time",
    "cast_time": "Cast Time",
    "duration": "Duration",
    "pspeed": "Projectile Speed",
    "pradius": "Projectile Radius",
    "spread": "Spread",
    "radius": "Radius",
    "range_distance": "Range",
    "dps": "DPS",
    "hps": "HPS",
}


def build_manifest(hero_count: int, generated_at: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or _utc_now(),
        "source": API_ENDPOINT,
        "hero_count": hero_count,
        "data_files": {
            "hero_index": "heroes.index.json",
            "audit_summary": "audit-summary.json",
            "quality_report": "quality-report.json",
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
            "warnings_by_ability": warnings_by_ability(hero.abilities),
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
        "raw_display": {
            key: clean_display_text(value)
            for key, value in ability.raw.items()
        },
        "parse_warnings": ability.parse_warnings,
    }


def build_stat_detail(label: str, stat: StatValue) -> dict[str, Any]:
    return {
        "field": label,
        "label": STAT_LABELS.get(label, label.replace("_", " ").title()),
        "raw": stat.raw,
        "raw_display": clean_display_text(stat.raw),
        "value": stat.value,
        "min_value": stat.min_value,
        "max_value": stat.max_value,
        "unit": stat.unit,
        "confidence": stat.confidence,
        "warnings": stat.warnings,
        "components": [
            {
                "label": component.label,
                "raw": component.raw,
                "raw_display": clean_display_text(component.raw),
                "value": component.value,
                "min_value": component.min_value,
                "max_value": component.max_value,
                "unit": component.unit,
                "warnings": component.warnings,
                "notes": component.notes,
            }
            for component in stat.components
        ],
    }


def clean_display_text(value: object) -> str | None:
    if value is None:
        return None
    text = html.unescape(str(value))
    text = text.replace("Ã¢â‚¬â€œ", "-").replace("Ã¢â‚¬â€", "-")
    text = text.replace("â€“", "-").replace("â€”", "-").replace("âˆ’", "-")
    text = re.sub(r"<\s*br\s*/?\s*>", "; ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s*;\s*", "; ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_audit_summary(
    playable_hero_names: list[str],
    character_rows: list[dict[str, Any]],
    heroes: list[HeroStats],
    ability_rows: list[dict[str, Any]],
    validation: SourceValidation,
) -> dict[str, Any]:
    return all_audit_summary(playable_hero_names, character_rows, heroes, ability_rows, validation)


def build_quality_report(heroes: list[HeroStats], generated_at: str | None = None) -> dict[str, Any]:
    hero_entries = [build_quality_hero_entry(hero) for hero in heroes]
    warning_counter: Counter[str] = Counter()
    warnings_by_hero: dict[str, int] = {}
    zero_ability_heroes: list[str] = []
    many_warning_heroes: list[str] = []
    many_unparsed_heroes: list[str] = []
    component_heroes: list[str] = []

    for hero, entry in zip(heroes, hero_entries, strict=True):
        warning_counter.update(
            warning
            for ability in hero.abilities
            for warning in ability.parse_warnings
        )
        warnings_by_hero[hero.name] = entry["warning_count"]
        if entry["ability_count"] == 0:
            zero_ability_heroes.append(hero.name)
        if entry["warning_count"] >= 10:
            many_warning_heroes.append(hero.name)
        if entry["parsed_stat_count"] and entry["confidence_counts"]["unparsed"] / entry["parsed_stat_count"] >= 0.75:
            many_unparsed_heroes.append(hero.name)
        if entry["component_stat_count"]:
            component_heroes.append(hero.name)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or _utc_now(),
        "summary": {
            "hero_count": len(heroes),
            "ability_count": sum(entry["ability_count"] for entry in hero_entries),
            "parsed_stat_count": sum(entry["parsed_stat_count"] for entry in hero_entries),
            "warning_count": sum(entry["warning_count"] for entry in hero_entries),
            "component_stat_count": sum(entry["component_stat_count"] for entry in hero_entries),
        },
        "heroes": hero_entries,
        "warnings": {
            "most_common": [
                {"warning": warning, "count": count}
                for warning, count in warning_counter.most_common(20)
            ],
            "by_hero": warnings_by_hero,
        },
        "coverage_flags": {
            "heroes_with_zero_abilities": zero_ability_heroes,
            "heroes_with_many_warnings": many_warning_heroes,
            "heroes_with_many_unparsed_stats": many_unparsed_heroes,
            "heroes_with_component_stats": component_heroes,
        },
    }


def build_quality_hero_entry(hero: HeroStats) -> dict[str, Any]:
    confidence_counts = count_confidences([hero])
    parsed_stat_count = sum(len(ability.parsed) for ability in hero.abilities)
    return {
        "name": hero.name,
        "slug": hero_slug(hero.name),
        "role": hero.role,
        "ability_count": len(hero.abilities),
        "parsed_stat_count": parsed_stat_count,
        "warning_count": sum(len(ability.parse_warnings) for ability in hero.abilities),
        "component_stat_count": sum(
            1
            for ability in hero.abilities
            for stat in ability.parsed.values()
            if stat.components
        ),
        "confidence_counts": {key: confidence_counts[key] for key in ("high", "medium", "low", "unparsed")},
    }


def write_web_data(
    heroes: list[HeroStats],
    audit_summary: dict[str, Any],
    output_dir: str | Path = DEFAULT_WEB_DATA_DIR,
) -> dict[str, Path]:
    base_dir = Path(output_dir)
    heroes_dir = base_dir / "heroes"
    heroes_dir.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now()
    manifest = build_manifest(hero_count=len(heroes), generated_at=generated_at)
    hero_index = build_hero_index(heroes)
    quality_report = build_quality_report(heroes, generated_at=generated_at)

    paths = {
        "manifest": base_dir / "manifest.json",
        "hero_index": base_dir / "heroes.index.json",
        "audit_summary": base_dir / "audit-summary.json",
        "quality_report": base_dir / "quality-report.json",
    }
    _write_json(paths["manifest"], manifest)
    _write_json(paths["hero_index"], hero_index)
    _write_json(paths["audit_summary"], audit_summary)
    _write_json(paths["quality_report"], quality_report)

    for hero in heroes:
        _write_json(heroes_dir / f"{hero_slug(hero.name)}.json", build_hero_detail(hero))

    return paths


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
