from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from .models import AbilityStats, HeroStats
from .normalize import _canonicalize_keys, clean_text, normalize_selected
from .parse_stats import EMPTY_VALUES


CONFIDENCE_ORDER = ("high", "medium", "low", "unparsed")


@dataclass
class SourceValidation:
    playable_missing_from_characters: list[str]
    playable_missing_from_abilities: list[str]
    extra_character_rows: list[str]
    extra_ability_hero_names: list[str]


def compare_source_sets(
    playable_hero_names: Iterable[str],
    character_rows: Iterable[dict[str, Any]],
    ability_rows: Iterable[dict[str, Any]],
) -> SourceValidation:
    playable = _name_map(playable_hero_names)
    characters = _name_map(_row_name(row, "name") for row in character_rows)
    abilities = _name_map(_row_name(row, "hero_name") for row in ability_rows)

    return SourceValidation(
        playable_missing_from_characters=_sorted_originals(playable.keys() - characters.keys(), playable),
        playable_missing_from_abilities=_sorted_originals(playable.keys() - abilities.keys(), playable),
        extra_character_rows=_sorted_originals(characters.keys() - playable.keys(), characters),
        extra_ability_hero_names=_sorted_originals(abilities.keys() - playable.keys(), abilities),
    )


def build_all_audit(
    playable_hero_names: list[str],
    character_rows: list[dict[str, Any]],
    ability_rows: list[dict[str, Any]],
) -> tuple[list[HeroStats], SourceValidation]:
    heroes = normalize_selected(character_rows, ability_rows, playable_hero_names)
    return heroes, compare_source_sets(playable_hero_names, character_rows, ability_rows)


def render_hero_audit(hero: HeroStats, ability_row_count: int) -> str:
    summary = hero_audit_summary(hero, ability_row_count)

    lines = [
        f"Hero audit: {summary['hero_name']}",
        f"Role: {_value_or_dash(summary['role'])} / {_value_or_dash(summary['sub_role'])}",
        f"Ability rows fetched: {summary['ability_rows']}",
        f"Parsed stat fields: {summary['parsed_stat_fields']}",
        "Confidence counts: " + _format_confidences(Counter(summary["confidence_counts"])),
        "",
        "Non-empty raw fields left unparsed:",
    ]
    lines.extend(_format_list(summary["non_empty_unparsed_fields"], empty="  None"))
    lines.extend(["", "Parse warnings by ability:"])
    lines.extend(_format_grouped_warnings(summary["warnings_by_ability"]))
    return "\n".join(lines)


def render_all_audit(
    playable_hero_names: list[str],
    character_rows: list[dict[str, Any]],
    heroes: list[HeroStats],
    ability_rows: list[dict[str, Any]],
    validation: SourceValidation,
) -> str:
    summary = all_audit_summary(playable_hero_names, character_rows, heroes, ability_rows, validation)
    source_validation = summary["source_validation"]

    lines = [
        "All-heroes audit",
        f"Playable heroes: {summary['totals']['playable_heroes']}",
        f"Characters rows: {summary['totals']['character_rows']}",
        f"Abilities hero groups: {summary['totals']['ability_hero_groups']}",
        f"Total ability rows: {summary['totals']['ability_rows']}",
        f"Total parsed stat fields: {summary['totals']['parsed_stat_fields']}",
        "Confidence counts: " + _format_confidences(Counter(summary["confidence_counts"])),
        "",
        f"Heroes missing metadata ({len(source_validation['heroes_missing_metadata'])}):",
    ]
    lines.extend(_format_list(source_validation["heroes_missing_metadata"], limit=50, empty="  None"))
    lines.extend(["", f"Heroes missing abilities ({len(source_validation['heroes_missing_abilities'])}):"])
    lines.extend(_format_list(source_validation["heroes_missing_abilities"], limit=50, empty="  None"))
    lines.extend(["", f"Normalized heroes with zero abilities ({len(summary['heroes_with_zero_abilities'])}):"])
    lines.extend(_format_list(summary["heroes_with_zero_abilities"], limit=50, empty="  None"))
    lines.extend(["", f"Ability hero names not in playable hero list ({len(source_validation['extra_ability_hero_names'])}):"])
    lines.extend(_format_list(source_validation["extra_ability_hero_names"], limit=50, empty="  None"))
    lines.extend(["", f"Extra Characters rows not in playable hero list ({len(source_validation['extra_character_rows'])}):"])
    lines.extend(_format_list(source_validation["extra_character_rows"], limit=50, empty="  None"))
    lines.extend(["", "Most common parse warnings:"])
    if summary["most_common_parse_warnings"]:
        lines.extend(
            f"  {entry['count']}x {entry['warning']}"
            for entry in summary["most_common_parse_warnings"]
        )
    else:
        lines.append("  None")
    return "\n".join(lines)


def hero_audit_summary(hero: HeroStats, ability_row_count: int) -> dict[str, Any]:
    confidence_counts = count_confidences([hero])
    return {
        "scope": "hero",
        "hero_name": hero.name,
        "role": hero.role,
        "sub_role": hero.sub_role,
        "ability_rows": ability_row_count,
        "parsed_stat_fields": sum(confidence_counts.values()),
        "confidence_counts": _plain_confidence_counts(confidence_counts),
        "non_empty_unparsed_fields": non_empty_unparsed_fields(hero.abilities),
        "warnings_by_ability": warnings_by_ability(hero.abilities),
    }


def all_audit_summary(
    playable_hero_names: list[str],
    character_rows: list[dict[str, Any]],
    heroes: list[HeroStats],
    ability_rows: list[dict[str, Any]],
    validation: SourceValidation,
) -> dict[str, Any]:
    confidence_counts = count_confidences(heroes)
    warning_counts = Counter(
        warning
        for hero in heroes
        for ability in hero.abilities
        for warning in ability.parse_warnings
    )
    ability_group_count = len(_name_map(_row_name(row, "hero_name") for row in ability_rows))
    return {
        "scope": "all",
        "totals": {
            "playable_heroes": len(playable_hero_names),
            "character_rows": len(character_rows),
            "ability_hero_groups": ability_group_count,
            "ability_rows": len(ability_rows),
            "parsed_stat_fields": sum(confidence_counts.values()),
        },
        "confidence_counts": _plain_confidence_counts(confidence_counts),
        "heroes_with_zero_abilities": [hero.name for hero in heroes if not hero.abilities],
        "source_validation": {
            "heroes_missing_metadata": validation.playable_missing_from_characters,
            "heroes_missing_abilities": validation.playable_missing_from_abilities,
            "extra_character_rows": validation.extra_character_rows,
            "extra_ability_hero_names": validation.extra_ability_hero_names,
        },
        "most_common_parse_warnings": [
            {"warning": warning, "count": count}
            for warning, count in warning_counts.most_common(10)
        ],
    }


def count_confidences(heroes: Iterable[HeroStats]) -> Counter[str]:
    counts: Counter[str] = Counter({confidence: 0 for confidence in CONFIDENCE_ORDER})
    for hero in heroes:
        for ability in hero.abilities:
            for stat in ability.parsed.values():
                counts[stat.confidence] += 1
    return counts


def non_empty_unparsed_fields(abilities: Iterable[AbilityStats]) -> list[str]:
    fields: list[str] = []
    for ability in abilities:
        for field, stat in ability.parsed.items():
            raw = clean_text(stat.raw)
            if stat.confidence == "unparsed" and raw and raw.lower() not in EMPTY_VALUES:
                fields.append(f"{ability.name}.{field}: {raw}")
    return fields


def warnings_by_ability(abilities: Iterable[AbilityStats]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for ability in abilities:
        if ability.parse_warnings:
            grouped[ability.name].extend(ability.parse_warnings)
    return dict(grouped)


def _row_name(row: dict[str, Any], canonical_key: str) -> str:
    return clean_text(_canonicalize_keys(row).get(canonical_key)) or ""


def _name_map(names: Iterable[str]) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for name in names:
        cleaned = clean_text(name)
        if cleaned:
            mapped[cleaned.casefold()] = cleaned
    return mapped


def _sorted_originals(keys: Iterable[str], originals: dict[str, str]) -> list[str]:
    return sorted((originals[key] for key in keys), key=str.casefold)


def _format_confidences(counts: Counter[str]) -> str:
    return ", ".join(f"{confidence}={counts[confidence]}" for confidence in CONFIDENCE_ORDER)


def _plain_confidence_counts(counts: Counter[str]) -> dict[str, int]:
    return {confidence: counts[confidence] for confidence in CONFIDENCE_ORDER}


def _format_list(values: list[str], limit: int | None = None, empty: str = "  None") -> list[str]:
    if not values:
        return [empty]
    shown = values if limit is None else values[:limit]
    lines = [f"  - {value}" for value in shown]
    if limit is not None and len(values) > limit:
        lines.append(f"  ... {len(values) - limit} more")
    return lines


def _format_grouped_warnings(grouped: dict[str, list[str]]) -> list[str]:
    if not grouped:
        return ["  None"]
    lines: list[str] = []
    for ability_name in sorted(grouped, key=str.casefold):
        lines.append(f"  {ability_name}:")
        lines.extend(f"    - {warning}" for warning in grouped[ability_name])
    return lines


def _value_or_dash(value: str | None) -> str:
    return value if value else "-"
