from __future__ import annotations

import html
import re
from typing import Callable

from .models import StatValue


EMPTY_VALUES = {"", "-", "n/a", "na", "none", "unknown", "varies"}
COMPLEX_DAMAGE_WARNING = (
    "Partial parse only: this stat has multiple components and value is not the full damage model."
)


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


def unparsed(raw: object, warning: str | None = None) -> StatValue:
    text = clean_text(raw)
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
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:-|to)\s*(-?\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if not match:
        return None
    first = _number(match.group(1))
    second = _number(match.group(2))
    return (min(first, second), max(first, second))


def _single_number_with_unit(raw: object, unit: str, label: str) -> StatValue:
    blank = _blank(raw)
    if blank:
        return blank
    text = clean_text(raw) or ""
    if "/" in text or "+" in text or "," in text:
        return unparsed(raw, f"{label} has multiple components and was left unparsed.")
    matches = re.findall(r"-?\d+(?:\.\d+)?", text)
    if len(matches) > 1:
        return StatValue(
            raw=str(raw),
            value=_number(matches[0]),
            unit=unit,
            confidence="low",
            warnings=[f"{label} has multiple values; only the first number was parsed."],
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
    return _single_number_with_unit(raw, "seconds", "duration")


def parse_reload_time(raw: object) -> StatValue:
    return _single_number_with_unit(raw, "seconds", "reload time")


def parse_ammo(raw: object) -> StatValue:
    blank = _blank(raw)
    if blank:
        return blank
    text = clean_text(raw) or ""
    if re.search(r"infinite|unlimited", text, re.IGNORECASE):
        return StatValue(raw=str(raw), value="infinite", unit="rounds", confidence="high")
    value = _first_number(text)
    if value is None:
        return unparsed(raw, "Could not parse ammo.")
    return StatValue(raw=str(raw), value=value, unit="rounds", confidence="high")


def parse_charges(raw: object) -> StatValue:
    blank = _blank(raw)
    if blank:
        return blank
    text = clean_text(raw) or ""
    value = _first_number(text)
    if value is None:
        return unparsed(raw, "Could not parse charges.")
    return StatValue(raw=str(raw), value=value, unit="charges", confidence="high")


def parse_damage(raw: object) -> StatValue:
    blank = _blank(raw)
    if blank:
        return blank
    text = clean_text(raw) or ""
    number_range = _range(text)
    warnings: list[str] = []
    confidence = "high"
    is_complex = _is_complex_damage(text)
    if is_complex:
        warnings.append(COMPLEX_DAMAGE_WARNING)
        confidence = "low"
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


def parse_falloff_range(raw: object) -> StatValue:
    blank = _blank(raw)
    if blank:
        return blank
    text = clean_text(raw) or ""
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
    text = clean_text(raw) or ""
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
    text = clean_text(raw) or ""
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
    value = parse_damage(raw)
    value.unit = "healing"
    return value


def parse_dps_hps(raw: object) -> StatValue:
    blank = _blank(raw)
    if blank:
        return blank
    text = clean_text(raw) or ""
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
