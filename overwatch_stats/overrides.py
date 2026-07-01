"""Programmatic corrections applied to generated website data.

Raw Cargo rows are never mutated.  Each override patches the generated base data or
a named ruleset and is recorded in ``overrides_applied`` for source inspection.
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
        {"id": "6v6", "label": "6v6", "status": "active"},
    ],
}

# Shape:
# "hero-slug": [{"ruleset": "6v6", "path": ["health", "armor"],
#                 "value": 100, "reason": "...", "source": "..."}]
# Prefer ability_index for ability stats. A readable name/slot/type selector is
# also supported: ["abilities", {"ability_index": 0}, "stats", "damage", ...].
HERO_OVERRIDES: dict[str, list[dict[str, Any]]] = {}


def build_ruleset_data(hero_slug: str, base: dict[str, Any]) -> dict[str, Any]:
    """Return immutable base data plus sparse per-ruleset patches and provenance."""
    ruleset_overrides: dict[str, dict[str, Any]] = {"6v6": {}}
    applied: list[dict[str, Any]] = []
    for correction in HERO_OVERRIDES.get(hero_slug, []):
        item = deepcopy(correction)
        ruleset = item.pop("ruleset", "5v5")
        path = item.pop("path")
        value = item.pop("value")
        target = base if ruleset == RULESETS["default"] else ruleset_overrides.setdefault(ruleset, {})
        _set_path(target, path, value)
        applied.append({"ruleset": ruleset, "path": path, "value": value, **item})
    return {"base": base, "ruleset_overrides": ruleset_overrides, "overrides_applied": applied}


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
