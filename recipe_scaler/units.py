"""Quantities, fractions and unit conversion for recipe scaling.

No dependencies: everything is exact rational arithmetic with `fractions`
and a small conversion table for the units a kitchen actually uses.
"""
import re
from fractions import Fraction

# dimension -> {unit: (factor to base, base unit)}
# base units: volume = ml, mass = g, temperature = C
# metric-friendly conversion factors: the US teaspoon is defined as
# ~4.93 ml and the US tablespoon as three of those, but recipes round to
# the familiar 5 ml / 15 ml, so those are what we use.
VOLUME = {
    "ml": (Fraction(1), "ml"),
    "l": (Fraction(1000), "ml"),
    "tsp": (Fraction(5), "ml"),
    "tbsp": (Fraction(15), "ml"),
    "cup": (Fraction(240), "ml"),
    "pint": (Fraction(473176, 1000), "ml"),
    "quart": (Fraction(946352, 1000), "ml"),
    "gallon": (Fraction(3785), "ml"),
    "floz": (Fraction(29574, 1000), "ml"),
    "stick": (Fraction(118), "ml"),  # half a cup of butter
}

MASS = {
    "g": (Fraction(1), "g"),
    "kg": (Fraction(1000), "g"),
    "oz": (Fraction(28350, 1000), "g"),
    "lb": (Fraction(453592, 1000), "g"),
}

# case-insensitive aliases
ALIASES = {
    "g": "g", "gr": "g", "gram": "g", "grams": "g",
    "kg": "kg", "kilo": "kg", "kilos": "kg", "kilogram": "kg",
    "oz": "oz", "ounce": "oz", "ounces": "oz",
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
    "ml": "ml", "milliliter": "ml", "milliliters": "ml",
    "l": "l", "liter": "l", "liters": "l", "litre": "l", "litres": "l",
    "tsp": "tsp", "tsps": "tsp", "teaspoon": "tsp", "teaspoons": "tsp",
    "tbsp": "tbsp", "tbsps": "tbsp", "tablespoon": "tbsp", "tablespoons": "tbsp",
    "cup": "cup", "cups": "cup", "c": "cup",
    "pint": "pint", "pints": "pint", "pt": "pint",
    "quart": "quart", "quarts": "quart", "qt": "quart",
    "gallon": "gallon", "gallons": "gallon", "gal": "gallon",
    "fl oz": "floz", "floz": "floz", "fl-oz": "floz",
    "stick": "stick", "sticks": "stick",
    "pinch": None,  # handled specially: too small to scale numerically
}

PINCHES = {"pinch": Fraction(1, 16), "pinches": Fraction(1, 16)}

TEMPERATURE_UNITS = {"c", "°c", "f", "°f", "fahrenheit", "celsius"}

# a count unit: eggs, cloves, slices — scaled as plain numbers
COUNT_UNITS = {"", "clove", "cloves", "slice", "slices", "piece", "pieces",
               "egg", "eggs", "can", "cans", "package", "packages", "bunch",
               "bunches", "head", "heads", "sprig", "sprigs", "handful"}

QUANTITY_RE = re.compile(
    r"^\s*(?P<value>\d+\s+\d+/\d+|\d+/\d+|\d*\.\d+|\d+)"
    r"(?:\s+(?P<unit>[a-zA-Z°]{1,12}(?:\s+oz)?))?\s*$"
)


class ParseError(ValueError):
    pass


def parse_quantity(text):
    """Parse '1 1/2 cups', '0.5 kg', '3' into (Fraction, unit)."""
    match = QUANTITY_RE.match(text)
    if not match:
        raise ParseError(f"cannot read a quantity from {text!r}")
    value_text = match.group("value").strip()
    unit_text = re.sub(r"\s+", " ", (match.group("unit") or "").strip().lower())

    try:
        if " " in value_text:  # mixed number: whole + fraction
            whole, frac = value_text.split()
            value = Fraction(whole) + Fraction(frac)
        else:
            value = Fraction(value_text)
    except (ZeroDivisionError, ValueError) as exc:
        raise ParseError(f"{value_text!r} is not a number: {exc}") from exc

    if unit_text in PINCHES:
        return value * PINCHES[unit_text], "tsp"
    canonical = ALIASES.get(unit_text)
    if canonical is None:
        if unit_text in COUNT_UNITS:
            return value, unit_text
        if unit_text in TEMPERATURE_UNITS:
            return value, unit_text
        # unknown unit: keep it, scale it as a count rather than dropping it
        return value, unit_text
    return value, canonical


def convert(value, from_unit, to_unit):
    """Convert between units of the same dimension; identity otherwise."""
    from_unit, to_unit = from_unit.lower(), to_unit.lower()
    if from_unit == to_unit:
        return value
    for table in (VOLUME, MASS):
        if from_unit in table and to_unit in table:
            from_factor, base = table[from_unit]
            to_factor, _ = table[to_unit]
            return value * from_factor / to_factor
    return value


def convert_temperature(value, from_unit, to_unit):
    """Celsius/Fahrenheit conversion for oven temperatures."""
    from_unit, to_unit = from_unit.lower().lstrip("°"), to_unit.lower().lstrip("°")
    if from_unit in ("c", "celsius") and to_unit in ("f", "fahrenheit"):
        return value * Fraction(9, 5) + Fraction(32)
    if from_unit in ("f", "fahrenheit") and to_unit in ("c", "celsius"):
        return (value - Fraction(32)) * Fraction(5, 9)
    return value


PLURALS = {"cup": "cups", "tbsp": "tbsp", "tsp": "tsp", "stick": "sticks",
           "g": "g", "kg": "kg", "ml": "ml", "l": "l", "oz": "oz", "lb": "lb",
           "pinch": "pinches"}


def _unit_for(unit, value):
    """Pluralize (or singularize) the unit to match the amount."""
    if value == 1 and unit in PLURALS.values():
        for singular, plural in PLURALS.items():
            if plural == unit:
                return singular
    if value != 1 and unit in ("cup", "stick", "pinch"):
        return PLURALS[unit]
    return unit


def format_quantity(value, unit="", style="fractions"):
    """Render a Fraction the way a recipe reads best.

    fractions -> 1 1/2      decimals -> 1.5      mixed -> 1-1/2
    """
    if style == "decimals":
        number = round(float(value), 2)
        text = f"{number:g}"
    else:
        if value.denominator == 1:
            text = str(value.numerator)
        elif style == "mixed":
            whole = value.numerator // value.denominator
            rest = Fraction(value.numerator - whole * value.denominator, value.denominator)
            text = f"{whole}-{rest.numerator}/{rest.denominator}"
        else:
            text = f"{value.numerator}/{value.denominator}"
            if value > 1 and value.numerator > value.denominator:
                whole = value.numerator // value.denominator
                rest = Fraction(value.numerator - whole * value.denominator, value.denominator)
                text = f"{whole} {rest.numerator}/{rest.denominator}"
    unit = unit or ""
    if not unit:
        return text
    if unit in COUNT_UNITS and value.denominator != 1:
        # nobody needs half an egg: counts are whole numbers
        text = str(int(value + Fraction(1, 2)))
    return f"{text} {_unit_for(unit, value)}"


# amounts below this round to zero when scaling down
ROUNDING_THRESHOLDS = (Fraction(1, 8), Fraction(1, 4), Fraction(1, 3),
                       Fraction(1, 2), Fraction(2, 3), Fraction(3, 4), 1)


def practical_round(value):
    """Snap a scaled amount to something a cook can measure."""
    if value <= 0:
        return Fraction(0)
    if value >= 3:  # large amounts stay exact enough at quarters
        return Fraction(round(value * 4), 4)
    for threshold in ROUNDING_THRESHOLDS:
        if abs(value - threshold) < Fraction(1, 16):
            return threshold
    return Fraction(round(value * 8), 8)


def scale_value(value, unit, factor, style="fractions", units="original",
                round_amounts=True):
    """Scale one amount, converting units when asked.

    Order matters: convert first, round last, so a "no unit" amount is
    never mistaken for a countable item and a pinch never vanishes.
    """
    scaled = value * Fraction(factor).limit_denominator(10000)

    if units == "metric":
        if unit in VOLUME:
            scaled, unit = convert(scaled, unit, "ml"), "ml"
        elif unit in MASS:
            scaled, unit = convert(scaled, unit, "g"), "g"
    elif units == "us":
        if unit == "ml":
            scaled, unit = convert(scaled, "ml", "tsp"), "tsp"
        elif unit == "g":
            scaled, unit = convert(scaled, "g", "oz"), "oz"

    if unit in COUNT_UNITS and unit:  # eggs, cloves, cans: whole items only
        scaled = Fraction(int(scaled + Fraction(1, 2)))
    elif round_amounts and scaled > 0:
        rounded = practical_round(scaled)
        # a rounding step must never erase the ingredient
        if rounded > 0:
            scaled = rounded
    if scaled == 0 and value > 0:
        # too small for the display unit: show it as a fraction of one
        if style == "decimals":
            return f"0.1 {unit}".strip()
        return f"1/{int(1 / scaled) if scaled else 1} {unit}".strip()
    return format_quantity(scaled, unit, style)
