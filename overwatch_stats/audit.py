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
    confidence_counts = count_confidences([hero])
    unparsed_raw = non_empty_unparsed_fields(hero.abilities)
    grouped_warnings = warnings_by_ability(hero.abilities)
    parsed_count = sum(confidence_counts.values())

    lines = [
        f"Hero audit: {hero.name}",
        f"Role: {_value_or_dash(hero.role)} / {_value_or_dash(hero.sub_role)}",
        f"Ability rows fetched: {ability_row_count}",
        f"Parsed stat fields: {parsed_count}",
        "Confidence counts: " + _format_confidences(confidence_counts),
        "",
        "Non-empty raw fields left unparsed:",
    ]
    lines.extend(_format_list(unparsed_raw, empty="  None"))
    lines.extend(["", "Parse warnings by ability:"])
    lines.extend(_format_grouped_warnings(grouped_warnings))
    return "\n".join(lines)


def render_all_audit(
    heroes: list[HeroStats],
    ability_rows: list[dict[str, Any]],
    validation: SourceValidation,
) -> str:
    confidence_counts = count_confidences(heroes)
    warning_counts = Counter(
        warning
        for hero in heroes
        for ability in hero.abilities
        for warning in ability.parse_warnings
    )
    parsed_count = sum(confidence_counts.values())
    zero_ability_heroes = [hero.name for hero in heroes if not hero.abilities]

    lines = [
        "All-heroes audit",
        f"Total heroes: {len(heroes)}",
        f"Total ability rows: {len(ability_rows)}",
        f"Total parsed stat fields: {parsed_count}",
        "Confidence counts: " + _format_confidences(confidence_counts),
        "",
        f"Heroes with zero abilities ({len(zero_ability_heroes)}):",
    ]
    lines.extend(_format_list(zero_ability_heroes, limit=50, empty="  None"))
    lines.extend(["", f"Ability hero names not in playable hero list ({len(validation.extra_ability_hero_names)}):"])
    lines.extend(_format_list(validation.extra_ability_hero_names, limit=50, empty="  None"))
    lines.extend(["", f"Playable heroes missing from Characters ({len(validation.playable_missing_from_characters)}):"])
    lines.extend(_format_list(validation.playable_missing_from_characters, limit=50, empty="  None"))
    lines.extend(["", f"Playable heroes missing from Abilities ({len(validation.playable_missing_from_abilities)}):"])
    lines.extend(_format_list(validation.playable_missing_from_abilities, limit=50, empty="  None"))
    lines.extend(["", f"Extra Characters rows not in playable hero list ({len(validation.extra_character_rows)}):"])
    lines.extend(_format_list(validation.extra_character_rows, limit=50, empty="  None"))
    lines.extend(["", "Most common parse warnings:"])
    if warning_counts:
        lines.extend(f"  {count}x {warning}" for warning, count in warning_counts.most_common(10))
    else:
        lines.append("  None")
    return "\n".join(lines)


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
