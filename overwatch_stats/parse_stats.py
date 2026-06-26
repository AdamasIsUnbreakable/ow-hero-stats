from __future__ import annotations

import html
import re
from typing import Callable

from .models import StatComponent, StatValue


EMPTY_VALUES = {"", "-", "n/a", "na", "none", "unknown", "varies"}
COMPLEX_DAMAGE_WARNING = "Complex damage model: raw value contains multiple components; no single damage value was parsed."
COMPONENT_DAMAGE_WARNING = "Complex damage model parsed into components; no single damage value was assigned."


def clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    text = html.unescape(text)
    text = text.replace("â€“", "-").replace("â€”", "-")
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    text = re.sub(r"<\s*br\s*/?\s*>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _stat_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    text = html.unescape(text)
    text = text.replace("Ã¢â‚¬â€œ", "-").replace("Ã¢â‚¬â€", "-")
    text = text.replace("â€“", "-").replace("â€”", "-").replace("âˆ’", "-")
    text = re.sub(r"<\s*br\s*/?\s*>", "; ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s*;\s*", "; ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def unparsed(raw: object, warning: str | None = None) -> StatValue:
    warnings = [warning] if warning else []
    return StatValue(raw=None if raw is None else str(raw), confidence="unparsed", warnings=warnings)


def _blank(raw: object) -> StatValue | None:
    text = clean_text(raw)
    if text is None or text.lower() in EMPTY_VALUES:
        return StatValue(raw=None if raw is None else str(raw), confidence="unparsed")
    return None


def _number(text: str) -> float | int:
    value = float(text.replace(",", ""))
    return int(value) if value.is_integer() else value


def _first_number(text: str) -> float | int | None:
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return _number(match.group(0)) if match else None


def _range(text: str) -> tuple[float | int, float | int] | None:
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:-|to|→)\s*(-?\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if not match:
        return None
    first = _number(match.group(1))
    second = _number(match.group(2))
    return (min(first, second), max(first, second))


def _single_number_with_unit(raw: object, unit: str, label: str) -> StatValue:
    blank = _blank(raw)
    if blank:
        return blank
    text = _stat_text(raw)
    lowered = text.lower()
    if lowered.startswith("none"):
        return StatValue(raw=str(raw), value="none", unit=unit, confidence="medium")
    matches = re.findall(r"-?\d+(?:\.\d+)?", text)
    if ("/" in text or "+" in text or "," in text) and len(matches) > 1:
        components = _numbered_components(text, unit)
        if components:
            return StatValue(
                raw=str(raw),
                value=None,
                unit=unit,
                confidence="medium",
                warnings=[f"{label} parsed into components; no single {unit} value was assigned."],
                components=components,
            )
        return unparsed(raw, f"{label} has multiple components and was left unparsed.")
    if len(matches) > 1:
        components = _numbered_components(text, unit)
        if components:
            return StatValue(
                raw=str(raw),
                value=None,
                unit=unit,
                confidence="medium",
                warnings=[f"{label} parsed into components; no single {unit} value was assigned."],
                components=components,
            )
        return StatValue(
            raw=str(raw),
            value=None,
            unit=unit,
            confidence="low",
            warnings=[f"{label} has multiple values; no single {unit} value was parsed."],
        )
    value = _first_number(text)
    if value is None:
        return unparsed(raw, f"Could not parse {label}.")
    confidence = "high" if re.search(re.escape(unit.rstrip("s")), text, re.IGNORECASE) else "medium"
    warnings = [] if confidence == "high" else [f"Parsed {label} number without an explicit {unit} unit."]
    return StatValue(raw=str(raw), value=value, unit=unit, confidence=confidence, warnings=warnings)


def parse_cooldown(raw: object) -> StatValue:
    return _single_number_with_unit(raw, "seconds", "cooldown")


def parse_duration(raw: object) -> StatValue:
    blank = _blank(raw)
    if blank:
        return blank
    text = _stat_text(raw)
    lowered = text.lower()
    if "∞" in text or re.search(r"\binfinite|unlimited\b", text, re.IGNORECASE):
        return StatValue(raw=str(raw), value="infinite", unit="duration", confidence="high")
    if lowered.startswith("until "):
        return StatValue(raw=str(raw), value=lowered.replace(" ", "_"), unit="duration", confidence="medium")
    return _single_number_with_unit(raw, "seconds", "duration")


def parse_reload_time(raw: object) -> StatValue:
    return _single_number_with_unit(raw, "seconds", "reload time")


def parse_ammo(raw: object) -> StatValue:
    blank = _blank(raw)
    if blank:
        return blank
    text = _stat_text(raw)
    if re.search(r"infinite|unlimited|∞", text, re.IGNORECASE):
        return StatValue(raw=str(raw), value="infinite", unit="rounds", confidence="high")
    value = _first_number(text)
    if value is None:
        return unparsed(raw, "Could not parse ammo.")
    return StatValue(raw=str(raw), value=value, unit="rounds", confidence="high")


def parse_charges(raw: object) -> StatValue:
    blank = _blank(raw)
    if blank:
        return blank
    text = _stat_text(raw)
    value = _first_number(text)
    if value is None:
        return unparsed(raw, "Could not parse charges.")
    return StatValue(raw=str(raw), value=value, unit="charges", confidence="high")


def parse_damage(raw: object) -> StatValue:
    blank = _blank(raw)
    if blank:
        return blank
    text = _stat_text(raw)
    components = _direct_plus_splash_components(text)
    if components:
        return StatValue(
            raw=str(raw),
            value=None,
            unit="damage",
            confidence="medium",
            warnings=[COMPONENT_DAMAGE_WARNING],
            components=components,
        )
    is_complex = _is_complex_damage(text)
    if is_complex:
        components = _complex_value_components(text, "damage")
        if components:
            warnings = [COMPONENT_DAMAGE_WARNING]
            if len(components) == 1:
                warnings.append(COMPLEX_DAMAGE_WARNING)
            return StatValue(
                raw=str(raw),
                value=None,
                unit="damage",
                confidence="medium" if len(components) > 1 else "low",
                warnings=warnings,
                components=components,
            )
        return StatValue(
            raw=str(raw),
            value=None,
            unit="damage",
            confidence="low",
            warnings=[COMPLEX_DAMAGE_WARNING],
        )
    number_range = _range(text)
    warnings: list[str] = []
    confidence = "high"
    if number_range:
        return StatValue(
            raw=str(raw),
            min_value=number_range[0],
            max_value=number_range[1],
            unit="damage",
            confidence=confidence,
            warnings=warnings,
        )
    value = _first_number(text)
    if value is None:
        return unparsed(raw, "Could not parse damage.")
    number_count = len(re.findall(r"-?\d+(?:\.\d+)?", text))
    if is_complex or number_count > 1:
        return StatValue(
            raw=str(raw),
            value=None,
            unit="damage",
            confidence="low",
            warnings=warnings or [COMPLEX_DAMAGE_WARNING],
        )
    return StatValue(raw=str(raw), value=value, unit="damage", confidence=confidence, warnings=warnings)


def _direct_plus_splash_components(text: str) -> list[StatComponent]:
    match = re.fullmatch(
        r"\s*(-?\d+(?:\.\d+)?)\s+(direct)\s*\+\s*(-?\d+(?:\.\d+)?)\s+(splash)\s*",
        text,
        re.IGNORECASE,
    )
    if not match:
        return []
    return [
        StatComponent(
            label=match.group(2).lower(),
            raw=f"{match.group(1)} {match.group(2).lower()}",
            value=_number(match.group(1)),
            unit="damage",
        ),
        StatComponent(
            label=match.group(4).lower(),
            raw=f"{match.group(3)} {match.group(4).lower()}",
            value=_number(match.group(3)),
            unit="damage",
        ),
    ]


def _complex_value_components(text: str, unit: str) -> list[StatComponent]:
    pieces = _complex_pieces(text)
    components = [_component_from_piece(piece, unit, index) for index, piece in enumerate(pieces, start=1)]
    return [component for component in components if component]


def _complex_pieces(text: str) -> list[str]:
    if ";" in text:
        return [piece.strip() for piece in text.split(";") if piece.strip()]
    return [text.strip()]


def _component_from_piece(piece: str, unit: str, index: int) -> StatComponent | None:
    range_match = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:-|to|→)\s*(-?\d+(?:\.\d+)?)", piece, re.IGNORECASE)
    first_number = re.search(r"-?\d+(?:\.\d+)?", piece)
    if not first_number:
        return None

    label = _component_label(piece)
    notes = _component_notes(piece)
    if label is None and not notes:
        return None
    label = label or f"component {index}"
    if range_match:
        first = _number(range_match.group(1))
        second = _number(range_match.group(2))
        return StatComponent(
            label=label,
            raw=piece,
            min_value=min(first, second),
            max_value=max(first, second),
            unit=unit,
            notes=notes,
        )

    return StatComponent(
        label=label,
        raw=piece,
        value=_number(first_number.group(0)),
        unit=unit,
        notes=notes,
    )


def _component_label(piece: str) -> str | None:
    colon_match = re.match(r"\s*([A-Za-z][^:]{1,40}):", piece)
    if colon_match:
        return clean_text(colon_match.group(1))

    parenthetical = re.search(r"\(([^)]+)\)", piece)
    if parenthetical:
        return clean_text(parenthetical.group(1))

    lowered = piece.lower()
    label_patterns = [
        ("direct hit", r"\bdirect hit\b"),
        ("direct", r"\bdirect\b"),
        ("splash", r"\bsplash\b"),
        ("explosion", r"\bexplosion\b"),
        ("impact", r"\bimpact\b"),
        ("self", r"\bself\b"),
        ("enemy", r"\benemy\b"),
        ("over time", r"\bover\s+\d"),
        ("per second", r"\bper\s+second\b"),
        ("total", r"\btotal\b"),
        ("per projectile", r"\bper\s+projectile\b"),
        ("per pellet", r"\bper\s+pellet\b"),
        ("per shot", r"\bper\s+shot\b"),
        ("per volley", r"\bper\s+volley\b"),
    ]
    for label, pattern in label_patterns:
        if re.search(pattern, lowered):
            return label
    return None


def _component_notes(piece: str) -> list[str]:
    notes: list[str] = []
    over_time = re.search(r"\bover\s+\d+(?:\.\d+)?\s*(?:seconds?|s\.?)", piece, re.IGNORECASE)
    if over_time:
        notes.append(clean_text(over_time.group(0)) or over_time.group(0))
    if "→" in piece:
        notes.append("scales between listed values")
    return notes


def parse_falloff_range(raw: object) -> StatValue:
    blank = _blank(raw)
    if blank:
        return blank
    text = _stat_text(raw)
    number_range = _range(text)
    if number_range:
        return StatValue(raw=str(raw), min_value=number_range[0], max_value=number_range[1], unit="meters", confidence="high")
    value = _first_number(text)
    if value is None:
        return unparsed(raw, "Could not parse falloff range.")
    return StatValue(
        raw=str(raw),
        value=value,
        unit="meters",
        confidence="medium",
        warnings=["Parsed falloff range as a single distance."],
    )


def parse_fire_rate(raw: object) -> StatValue:
    blank = _blank(raw)
    if blank:
        return blank
    text = _stat_text(raw)
    number_range = _range(text)
    if number_range:
        return StatValue(raw=str(raw), min_value=number_range[0], max_value=number_range[1], unit="shots_per_second", confidence="medium")
    value = _first_number(text)
    if value is None:
        return unparsed(raw, "Could not parse fire rate.")
    return StatValue(raw=str(raw), value=value, unit="shots_per_second", confidence="high")


def parse_projectile_speed(raw: object) -> StatValue:
    blank = _blank(raw)
    if blank:
        return blank
    text = _stat_text(raw)
    value = _first_number(text)
    if value is None:
        return unparsed(raw, "Could not parse projectile speed.")
    confidence = "high" if re.search(r"(m/s|meter)", text, re.IGNORECASE) else "medium"
    warnings = [] if confidence == "high" else ["Parsed projectile speed without an explicit meters-per-second unit."]
    return StatValue(raw=str(raw), value=value, unit="meters_per_second", confidence=confidence, warnings=warnings)


def parse_projectile_radius(raw: object) -> StatValue:
    return _single_number_with_unit(raw, "meters", "projectile radius")


def parse_spread(raw: object) -> StatValue:
    return _single_number_with_unit(raw, "degrees", "spread")


def parse_healing(raw: object) -> StatValue:
    blank = _blank(raw)
    if blank:
        return blank
    text = _stat_text(raw)
    if re.search(r"\b(full health|revives?|restores full health)\b", text, re.IGNORECASE):
        return StatValue(raw=str(raw), value="full_health", unit="health", confidence="medium")
    value = parse_damage(raw)
    value.unit = "healing"
    for component in value.components:
        component.unit = "healing"
    return value


def _numbered_components(text: str, unit: str) -> list[StatComponent]:
    components: list[StatComponent] = []
    matches = list(
        re.finditer(
            r"(?P<value>-?\d+(?:\.\d+)?)\s*(?P<unit>seconds?|sec(?:onds?)?|s\.?|degrees?|meters?|m)?(?:\s*\((?P<label>[^)]+)\))?(?:\s*(?P<tail>per\s+[^;,+]+))?",
            text,
            re.IGNORECASE,
        ),
    )
    if len(matches) < 2:
        return []

    for index, match in enumerate(matches, start=1):
        matched_unit = match.group("unit") or ""
        if matched_unit and not _component_unit_matches(unit, matched_unit):
            continue
        label = match.group("label") or match.group("tail") or f"component {index}"
        components.append(
            StatComponent(
                label=clean_text(label) or f"component {index}",
                raw=match.group(0).strip(),
                value=_number(match.group("value")),
                unit=unit,
            ),
        )
    return components if len(components) >= 2 else []


def _component_unit_matches(unit: str, matched_unit: str) -> bool:
    normalized = matched_unit.lower().rstrip(".")
    aliases = {
        "seconds": {"s", "sec", "second", "seconds"},
        "degrees": {"degree", "degrees"},
        "meters": {"m", "meter", "meters"},
    }
    return normalized in aliases.get(unit, {unit.rstrip("s"), unit})


def parse_dps_hps(raw: object) -> StatValue:
    blank = _blank(raw)
    if blank:
        return blank
    text = _stat_text(raw)
    number_range = _range(text)
    if number_range:
        return StatValue(raw=str(raw), min_value=number_range[0], max_value=number_range[1], unit="per_second", confidence="high")
    value = _first_number(text)
    if value is None:
        return unparsed(raw, "Could not parse per-second stat.")
    return StatValue(raw=str(raw), value=value, unit="per_second", confidence="high")


def _is_complex_damage(text: str) -> bool:
    if re.search(r"\b(direct|splash|impact|explosion)\b|\+", text, re.IGNORECASE):
        return True
    if "→" in text:
        return True
    if ";" in text:
        return True
    if re.search(r"\bover\s+\d+(?:\.\d+)?\s*(?:seconds?|s\.?)", text, re.IGNORECASE):
        return True
    if re.search(r"\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?", text):
        return True
    if re.search(r"\d+(?:\.\d+)?\s*,\s*\d+(?:\.\d+)?", text):
        return True
    return False


PARSERS: dict[str, Callable[[object], StatValue]] = {
    "cooldown": parse_cooldown,
    "duration": parse_duration,
    "reload_time": parse_reload_time,
    "ammo": parse_ammo,
    "charges": parse_charges,
    "damage": parse_damage,
    "damage_falloff_range": parse_falloff_range,
    "fire_rate": parse_fire_rate,
    "pspeed": parse_projectile_speed,
    "pradius": parse_projectile_radius,
    "spread": parse_spread,
    "heal": parse_healing,
    "dps": parse_dps_hps,
    "hps": parse_dps_hps,
}
