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
from .parse_stats import EMPTY_VALUES, clean_text
from .overrides import RULESETS, build_ruleset_data


SCHEMA_VERSION = "2.0.0"
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
    "ult_cost": "Ultimate Cost",
    "ultimate_cost": "Ultimate Cost",
    "perk_cost": "Perk Level-up Cost",
    "barrier_health": "Barrier Health",
    "overhealth": "Overhealth",
    "health_given": "Health Given",
}
DISPLAY_UNITS = {
    "shots_per_second": "shots/s",
    "meters_per_second": "m/s",
    "per_second": "/s",
    "meters": "m",
    "seconds": "s",
    "degrees": "\u00b0",
    "damage": "damage",
    "healing": "healing",
    "rounds": "rounds",
    "charges": "charges",
    "percent": "%",
    "points": "points",
    "health": "health",
}
FIELD_DISPLAY_UNITS = {
    ("dps", "per_second"): "damage/s",
    ("hps", "per_second"): "healing/s",
}


def build_manifest(hero_count: int, generated_at: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or _utc_now(),
        "source": API_ENDPOINT,
        "hero_count": hero_count,
        "rulesets": RULESETS,
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
    base = {
        "role": hero.role,
        "sub_role": hero.sub_role,
        "health": hero.health,
        "abilities": [
            build_ability_detail(ability, ability_index)
            for ability_index, ability in enumerate(hero.abilities)
        ],
    }
    ruleset_data = build_ruleset_data(slug, base)
    return {
        "schema_version": SCHEMA_VERSION,
        "name": hero.name,
        "slug": slug,
        **base,
        **ruleset_data,
        "source_generated_at": hero.fetched_at or None,
        "audit": {
            "warning_count": sum(len(ability.parse_warnings) for ability in hero.abilities),
            "confidence_counts": build_hero_index_entry(hero)["confidence_counts"],
            "warnings_by_ability": warnings_by_ability(hero.abilities),
        },
    }


def build_ability_detail(ability: AbilityStats, ability_index: int) -> dict[str, Any]:
    return {
        "ability_index": ability_index,
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
        "display_unit": display_unit(label, stat.unit),
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
                "display_unit": display_unit(label, component.unit),
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
    text = re.sub(r"\[\[(?:File|Image):[^\]]+\]\]", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\s*;\s*", "; ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def display_unit(field: str, unit: str | None) -> str | None:
    if unit is None:
        return None
    if (field, unit) in FIELD_DISPLAY_UNITS:
        return FIELD_DISPLAY_UNITS[(field, unit)]
    return DISPLAY_UNITS.get(unit, unit.replace("_", " "))


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
    icon_quality = build_icon_quality(heroes)
    perk_quality = build_perk_quality(heroes)
    warning_counter: Counter[tuple[str, str, str | None]] = Counter()
    warnings_by_hero: dict[str, int] = {}
    warnings_by_field: Counter[str] = Counter()
    empty_by_field: Counter[str] = Counter()
    unparsed_nonempty_by_field: Counter[str] = Counter()
    component_stats_by_field: Counter[str] = Counter()
    machine_units_by_unit: Counter[str] = Counter()
    display_units_by_unit: Counter[str] = Counter()
    stats_missing_display_unit: list[str] = []
    zero_ability_heroes: list[str] = []
    many_warning_heroes: list[str] = []
    many_unparsed_heroes: list[str] = []
    component_heroes: list[str] = []

    for hero, entry in zip(heroes, hero_entries, strict=True):
        warning_counter.update(_quality_warning_keys(hero))
        warnings_by_field.update(_stat_warning_fields(hero))
        empty_by_field.update(
            field
            for ability in hero.abilities
            for field, stat in ability.parsed.items()
            if stat.confidence == "unparsed" and is_empty_stat_raw(stat.raw)
        )
        unparsed_nonempty_by_field.update(
            field
            for ability in hero.abilities
            for field, stat in ability.parsed.items()
            if stat.confidence == "unparsed" and not is_empty_stat_raw(stat.raw)
        )
        component_stats_by_field.update(
            field
            for ability in hero.abilities
            for field, stat in ability.parsed.items()
            if stat.components
        )
        for ability in hero.abilities:
            for field, stat in ability.parsed.items():
                if stat.unit:
                    machine_units_by_unit[stat.unit] += 1
                    unit_display = display_unit(field, stat.unit)
                    if unit_display:
                        display_units_by_unit[unit_display] += 1
                    else:
                        stats_missing_display_unit.append(f"{hero.name}: {ability.name}: {field}")
                for component in stat.components:
                    if component.unit:
                        machine_units_by_unit[component.unit] += 1
                        component_display = display_unit(field, component.unit)
                        if component_display:
                            display_units_by_unit[component_display] += 1
                        else:
                            stats_missing_display_unit.append(f"{hero.name}: {ability.name}: {field}: {component.label}")
        warnings_by_hero[hero.name] = entry["warning_count"]
        if entry["ability_count"] == 0:
            zero_ability_heroes.append(hero.name)
        if entry["warning_count"] >= 10:
            many_warning_heroes.append(hero.name)
        if entry["unparsed_nonempty_stat_count"] >= 10:
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
            "missing_icon_count": icon_quality["missing_icon_count"],
        },
        "heroes": hero_entries,
        "warnings": {
            "most_common": [
                {
                    "warning": warning,
                    "count": count,
                    "level": level,
                    "field": field,
                }
                for (level, field, warning), count in warning_counter.most_common(20)
            ],
            "by_hero": warnings_by_hero,
        },
        "fields": {
            "warnings_by_field": dict(sorted(warnings_by_field.items())),
            "empty_by_field": dict(sorted(empty_by_field.items())),
            "unparsed_nonempty_by_field": dict(sorted(unparsed_nonempty_by_field.items())),
            "unparsed_by_field": dict(sorted(unparsed_nonempty_by_field.items())),
            "component_stats_by_field": dict(sorted(component_stats_by_field.items())),
            "machine_units_by_unit": dict(sorted(machine_units_by_unit.items())),
            "display_units_by_unit": dict(sorted(display_units_by_unit.items())),
        },
        "coverage_flags": {
            "heroes_with_zero_abilities": zero_ability_heroes,
            "heroes_with_many_warnings": many_warning_heroes,
            "heroes_with_many_unparsed_stats": many_unparsed_heroes,
            "heroes_with_component_stats": component_heroes,
            "stats_missing_display_unit": stats_missing_display_unit,
        },
        "icons": icon_quality,
        "perks": perk_quality,
        "asset_reports": {
            "ability_icon_coverage": "assets/abilities/coverage-report.json",
        },
    }


def build_icon_quality(heroes: list[HeroStats]) -> dict[str, Any]:
    by_hero: dict[str, list[dict[str, Any]]] = {}
    hero_details: dict[str, dict[str, Any]] = {}
    missing_count = 0
    for hero in heroes:
        missing_abilities: list[dict[str, Any]] = []
        missing_passives: list[dict[str, Any]] = []
        missing_perks: list[dict[str, Any]] = []
        for ability in hero.abilities:
            icon_value = _ability_raw_field(ability, "ability_image")
            reason = icon_asset_issue(icon_value)
            if not reason:
                continue
            record = {
                "ability": ability.name,
                "type": ability.type,
                "reason": reason,
                "source_value": icon_value,
            }
            ability_type = (ability.type or "").casefold()
            if "perk" in ability_type:
                missing_perks.append(record)
            elif "passive" in ability_type:
                missing_passives.append(record)
            else:
                missing_abilities.append(record)
        all_missing = missing_abilities + missing_passives + missing_perks
        if all_missing:
            by_hero[hero.name] = all_missing
            hero_details[hero.name] = {
                "missing_ability_icons": missing_abilities,
                "missing_passive_icons": missing_passives,
                "missing_perk_icons": missing_perks,
                "missing_icon_count": len(all_missing),
            }
            missing_count += len(all_missing)
    return {
        "heroes_with_missing_icons": by_hero,
        "by_hero": hero_details,
        "missing_icon_count": missing_count,
    }


def icon_asset_issue(value: object) -> str | None:
    text = clean_text(value)
    if not text:
        return "missing image asset"
    if re.fullmatch(r"[A-Za-z]{1,4}", text):
        return "text-only fallback"
    candidate = text.split("?", 1)[0].split("#", 1)[0]
    if not re.search(r"\.(?:png|webp|jpe?g|svg)$", candidate, re.IGNORECASE):
        return "not a real image asset"
    return None


def build_perk_quality(heroes: list[HeroStats]) -> dict[str, Any]:
    unexpected_minor: dict[str, dict[str, Any]] = {}
    unexpected_major: dict[str, dict[str, Any]] = {}
    for hero in heroes:
        minor = sorted(
            ability.name
            for ability in hero.abilities
            if "minor perk" in (ability.type or "").casefold()
        )
        major = sorted(
            ability.name
            for ability in hero.abilities
            if "major perk" in (ability.type or "").casefold()
        )
        if len(minor) != 2:
            unexpected_minor[hero.name] = {"count": len(minor), "perks": minor}
        if len(major) != 2:
            unexpected_major[hero.name] = {"count": len(major), "perks": major}
    return {
        "expected_minor_count": 2,
        "expected_major_count": 2,
        "heroes_with_unexpected_minor_count": unexpected_minor,
        "heroes_with_unexpected_major_count": unexpected_major,
    }


def _ability_raw_field(ability: AbilityStats, wanted_field: str) -> Any:
    wanted_key = re.sub(r"[^a-z0-9]", "", wanted_field.casefold())
    for key, value in ability.raw.items():
        key_normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
        if key_normalized == wanted_key:
            return value
    return None


def build_quality_hero_entry(hero: HeroStats) -> dict[str, Any]:
    confidence_counts = count_confidences([hero])
    parsed_stat_count = sum(len(ability.parsed) for ability in hero.abilities)
    empty_stat_count = sum(
        1
        for ability in hero.abilities
        for stat in ability.parsed.values()
        if stat.confidence == "unparsed" and is_empty_stat_raw(stat.raw)
    )
    unparsed_nonempty_stat_count = sum(
        1
        for ability in hero.abilities
        for stat in ability.parsed.values()
        if stat.confidence == "unparsed" and not is_empty_stat_raw(stat.raw)
    )
    ability_warning_count = sum(len(ability.parse_warnings) for ability in hero.abilities)
    stat_warning_count = sum(
        len(stat.warnings)
        for ability in hero.abilities
        for stat in ability.parsed.values()
    )
    return {
        "name": hero.name,
        "slug": hero_slug(hero.name),
        "role": hero.role,
        "ability_count": len(hero.abilities),
        "parsed_stat_count": parsed_stat_count,
        "empty_stat_count": empty_stat_count,
        "unparsed_nonempty_stat_count": unparsed_nonempty_stat_count,
        "ability_warning_count": ability_warning_count,
        "stat_warning_count": stat_warning_count,
        "warning_count": ability_warning_count + stat_warning_count,
        "component_stat_count": sum(
            1
            for ability in hero.abilities
            for stat in ability.parsed.values()
            if stat.components
        ),
        "confidence_counts": {key: confidence_counts[key] for key in ("high", "medium", "low", "unparsed")},
    }


def _quality_warning_keys(hero: HeroStats) -> list[tuple[str, str | None, str]]:
    keys: list[tuple[str, str | None, str]] = []
    for ability in hero.abilities:
        keys.extend(("ability", None, warning) for warning in ability.parse_warnings)
        for field, stat in ability.parsed.items():
            keys.extend(("stat", field, f"{field}: {warning}") for warning in stat.warnings)
    return keys


def _stat_warning_fields(hero: HeroStats) -> list[str]:
    return [
        field
        for ability in hero.abilities
        for field, stat in ability.parsed.items()
        for _warning in stat.warnings
    ]


def is_empty_stat_raw(raw: object) -> bool:
    text = clean_text(raw)
    return text is None or text.lower() in EMPTY_VALUES


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
