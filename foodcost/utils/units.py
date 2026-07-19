"""Unit registry and conversions.

Three dimensions are supported: weight (base oz-wt), volume (base oz-fl)
and count (base each). Recipe measures such as ``Pack (4 oz-wt)`` are
resolved to their parenthesized equivalent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# unit alias -> (dimension, factor to base unit)
_UNIT_TABLE: dict[str, tuple[str, float]] = {
    # weight -> oz-wt
    "OZ-WT": ("weight", 1.0), "OZ": ("weight", 1.0), "OUNCE": ("weight", 1.0),
    "LB": ("weight", 16.0), "LBS": ("weight", 16.0), "#": ("weight", 16.0),
    "POUND": ("weight", 16.0),
    "KG": ("weight", 35.274), "G": ("weight", 0.035274), "GRAM": ("weight", 0.035274),
    # volume -> oz-fl
    "OZ-FL": ("volume", 1.0), "FLOZ": ("volume", 1.0), "FL-OZ": ("volume", 1.0),
    "GAL": ("volume", 128.0), "GALLON": ("volume", 128.0),
    "QT": ("volume", 32.0), "QUART": ("volume", 32.0),
    "PT": ("volume", 16.0), "PINT": ("volume", 16.0),
    "CUP": ("volume", 8.0),
    "TBSP": ("volume", 0.5), "TSP": ("volume", 1.0 / 6.0),
    "ML": ("volume", 0.033814), "L": ("volume", 33.814), "LTR": ("volume", 33.814),
    # count -> each
    "EACH": ("count", 1.0), "EA": ("count", 1.0), "CT": ("count", 1.0),
    "PC": ("count", 1.0), "PCS": ("count", 1.0), "SLICE": ("count", 1.0),
    "DZ": ("count", 12.0), "DOZ": ("count", 12.0), "DOZEN": ("count", 12.0),
}

_PAREN_RE = re.compile(r"^(?P<name>[A-Za-z ]+)\((?P<qty>[\d.]+)\s*(?P<unit>[A-Za-z\-]+)\)")


@dataclass(frozen=True)
class Quantity:
    """A quantity resolved to a base unit within one dimension."""

    value: float
    dimension: str          # weight | volume | count | unknown
    base_unit: str          # oz-wt | oz-fl | each | raw unit string


_BASE_UNIT = {"weight": "oz-wt", "volume": "oz-fl", "count": "each"}


def parse_measure(qty: float, measure: str) -> Quantity:
    """Convert ``qty`` in ``measure`` to its base unit.

    Handles composite recipe measures like ``Pack (4 oz-wt)`` by
    multiplying through the parenthesized equivalent.
    """
    m = str(measure or "").strip()
    # Composite: "Pack (4 oz-wt)" / "Bag (5 Lb)" etc.
    paren = _PAREN_RE.match(m)
    if paren:
        inner_qty = float(paren.group("qty"))
        inner_unit = paren.group("unit")
        inner = parse_measure(qty * inner_qty, inner_unit)
        return inner

    key = m.upper().replace(" ", "")
    if key in _UNIT_TABLE:
        dim, factor = _UNIT_TABLE[key]
        return Quantity(qty * factor, dim, _BASE_UNIT[dim])
    return Quantity(qty, "unknown", m or "unit")


def convert(qty: float, from_unit: str, to_unit: str) -> float | None:
    """Convert between two units of the same dimension; None if impossible."""
    q = parse_measure(qty, from_unit)
    target = parse_measure(1.0, to_unit)
    if q.dimension == "unknown" or target.dimension != q.dimension:
        return None
    return q.value / target.value


def format_qty(value: float, base_unit: str) -> str:
    """Human-friendly rendering, promoting to larger units when sensible."""
    if base_unit == "oz-wt" and abs(value) >= 32:
        return f"{value / 16.0:,.1f} lb"
    if base_unit == "oz-fl" and abs(value) >= 256:
        return f"{value / 128.0:,.1f} gal"
    if base_unit == "each" and abs(value) >= 100:
        return f"{value:,.0f} ea"
    return f"{value:,.1f} {base_unit}"
