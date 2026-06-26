from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


Confidence = Literal["high", "medium", "low", "unparsed"]


@dataclass
class StatComponent:
    label: str
    raw: str | None
    value: float | int | str | None = None
    min_value: float | None = None
    max_value: float | None = None
    unit: str | None = None
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class StatValue:
    raw: str | None
    value: float | int | str | None = None
    min_value: float | None = None
    max_value: float | None = None
    unit: str | None = None
    confidence: Confidence = "unparsed"
    warnings: list[str] = field(default_factory=list)
    components: list[StatComponent] = field(default_factory=list)


@dataclass
class AbilityStats:
    name: str
    slot: str | None = None
    type: str | None = None
    shot_type: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    parsed: dict[str, StatValue] = field(default_factory=dict)
    parse_warnings: list[str] = field(default_factory=list)


@dataclass
class HeroStats:
    name: str
    role: str | None = None
    sub_role: str | None = None
    health: dict[str, int | None] = field(default_factory=dict)
    abilities: list[AbilityStats] = field(default_factory=list)
    source: str = "https://overwatch.fandom.com/api.php"
    fetched_at: str = ""


def to_plain_data(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, list):
        return [to_plain_data(item) for item in value]
    if isinstance(value, dict):
        return {key: to_plain_data(item) for key, item in value.items()}
    return value
