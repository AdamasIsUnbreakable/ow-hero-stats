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
# Ability stats use ["abilities", {"name": "Ability"}, "stats", "damage", ...].
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
    for part in path[:-1]:
        if isinstance(part, dict) and "name" in part:
            abilities = current.setdefault("abilities", [])
            current = next((ability for ability in abilities if ability.get("name") == part["name"]), None)
            if current is None:
                current = {"name": part["name"]}
                abilities.append(current)
        else:
            current = current.setdefault(str(part), {})
    current[str(path[-1])] = deepcopy(value)
