"""Programmatic corrections applied to generated website data.

Raw Cargo rows and the caller's source-derived base are never mutated. Corrections
patch a generated copy of ``base``. Every correction is recorded in
``overrides_applied`` for source inspection.
Add narrowly sourced corrections to ``HERO_OVERRIDES``; do not add display-only
hero checks to the frontend.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


RULESETS = {
    "default": "5v5",
    "available": [
        {"id": "5v5", "label": "5v5", "status": "active"},
    ],
}

# Shape:
# "hero-slug": [{"ruleset": "5v5", "path": ["health", "armor"],
#                 "value": 100, "reason": "...", "source": "..."}]
# Prefer ability_index for ability stats. A readable name/slot/type selector is
# also supported: ["abilities", {"ability_index": 0}, "stats", "damage", ...].
HERO_OVERRIDES: dict[str, list[dict[str, Any]]] = {}


def build_ruleset_data(hero_slug: str, base: dict[str, Any]) -> dict[str, Any]:
    """Return corrected default base, sparse non-default patches, and provenance."""
    source_base = deepcopy(base)
    generated_base = deepcopy(base)
    available_rulesets = {item["id"] for item in RULESETS["available"]}
    ruleset_overrides: dict[str, dict[str, Any]] = {
        ruleset: {} for ruleset in available_rulesets if ruleset != RULESETS["default"]
    }
    applied: list[dict[str, Any]] = []
    for correction in HERO_OVERRIDES.get(hero_slug, []):
        item = deepcopy(correction)
        ruleset = item.pop("ruleset", "5v5")
        path = item.pop("path")
        value = item.pop("value")
        if ruleset not in available_rulesets:
            raise ValueError(f"Unknown ruleset {ruleset!r} in override for {hero_slug!r}.")
        _validate_override_path(source_base, path, hero_slug)
        target = generated_base if ruleset == RULESETS["default"] else ruleset_overrides[ruleset]
        _set_path(target, path, value)
        applied.append({"ruleset": ruleset, "path": path, "value": value, **item})
    return {"base": generated_base, "ruleset_overrides": ruleset_overrides, "overrides_applied": applied}


def _validate_override_path(base: dict[str, Any], path: list[Any], hero_slug: str) -> None:
    if not path:
        raise ValueError(f"Override path for {hero_slug!r} cannot be empty.")
    for index, part in enumerate(path):
        if part != "abilities":
            continue
        if index + 1 >= len(path) or not isinstance(path[index + 1], dict):
            raise ValueError("Ability override path requires a selector immediately after 'abilities'.")
        selector = path[index + 1]
        matches = [ability for ability in base.get("abilities", []) if _selector_matches_patch(ability, selector)]
        if len(matches) != 1:
            identity = ", ".join(f"{key}={value!r}" for key, value in selector.items()) or "empty selector"
            reason = "missing" if not matches else f"ambiguous ({len(matches)} matches)"
            raise ValueError(f"Ability override for {hero_slug!r} is {reason}: {identity}.")


def _set_path(target: dict[str, Any], path: list[Any], value: Any) -> None:
    current: Any = target
    index = 0
    while index < len(path) - 1:
        part = path[index]
        if part == "abilities" and index + 1 < len(path) and isinstance(path[index + 1], dict):
            abilities = current.setdefault("abilities", [])
            if not isinstance(abilities, list):
                raise ValueError("Ability override path requires an abilities list.")
            current = _get_or_create_ability_patch(abilities, path[index + 1])
            index += 2
            continue
        if isinstance(part, dict):
            raise ValueError("Ability selector must immediately follow 'abilities'.")
        current = current.setdefault(str(part), {})
        index += 1
    current[str(path[-1])] = deepcopy(value)


def _get_or_create_ability_patch(
    abilities: list[dict[str, Any]],
    selector: dict[str, Any],
) -> dict[str, Any]:
    patch = next((item for item in abilities if _selector_matches_patch(item, selector)), None)
    if patch is None:
        patch = deepcopy(selector)
        abilities.append(patch)
    return patch


def _selector_matches_patch(patch: dict[str, Any], selector: dict[str, Any]) -> bool:
    if "ability_index" in selector:
        return patch.get("ability_index") == selector["ability_index"]
    fields = (
        ("name", "slot", "type")
        if all(field in selector for field in ("name", "slot", "type"))
        else ("name", "slot")
        if all(field in selector for field in ("name", "slot"))
        else ("name",)
    )
    return all(patch.get(field) == selector.get(field) for field in fields)
