"""Recipe parsing and scaling: read a markdown-ish recipe, scale every
ingredient by a factor, and write the result back out."""
import re
from fractions import Fraction

from .units import (ParseError, convert_temperature, format_quantity,
                    parse_quantity, scale_value)

INGREDIENT_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(?P<body>.+)$")
SERVINGS_RE = re.compile(r"serves\s+(?P<count>\d+)|(?P<count2>\d+)\s+servings",
                         re.IGNORECASE)
# an oven temperature: "180 C", "350°F"
TEMPERATURE_RE = re.compile(r"(?P<value>\d+)\s*°?\s*(?P<unit>[CF])\b")


class Recipe:
    def __init__(self, title, servings, ingredients, steps, notes=None):
        self.title = title
        self.servings = servings
        self.ingredients = ingredients
        self.steps = steps
        self.notes = notes or []

    def factor_for_servings(self, target):
        if not self.servings:
            raise ValueError("recipe does not state a serving count")
        return Fraction(target, self.servings)


def parse_recipe(text):
    """Split a recipe into title, servings, ingredients, steps and notes."""
    lines = text.splitlines()
    title = ""
    servings = None
    ingredients = []
    steps = []
    notes = []
    section = "preamble"

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith("#"):
            if stripped.startswith("## "):
                heading = stripped[3:].strip().lower()
                section = {"ingredients": "ingredients", "instructions": "steps",
                           "steps": "steps", "direction": "steps",
                           "directions": "steps", "notes": "notes",
                           "method": "steps"}.get(heading, section)
            else:
                title = title or stripped.lstrip("# ").strip()
                section = "title"
            continue

        if section == "title" and not title:
            title = stripped

        if section == "preamble" or section == "title":
            match = SERVINGS_RE.search(stripped)
            if match:
                count = match.group("count") or match.group("count2")
                servings = int(count)
                section = "preamble"
                continue

        if section == "preamble":
            section = "steps"
            steps.append(stripped)
            continue

        if section == "ingredients":
            match = INGREDIENT_RE.match(line)
            ingredients.append(match.group("body").strip() if match else stripped)
            continue

        if section == "notes":
            notes.append(stripped)
            continue

        steps.append(re.sub(r"^\d+[.)]\s*", "", stripped))

    if not title:
        title = "Recipe"
    return Recipe(title, servings, ingredients, steps, notes)


UNIT_WORDS = ("pinch", "pinches", "clove", "cloves", "slice", "slices",
              "cup", "cups", "tbsp", "tbsps", "tablespoon", "tablespoons",
              "tsp", "tsps", "teaspoon", "teaspoons", "g", "kg", "ml", "l",
              "oz", "lb", "lbs", "pound", "pounds", "ounce", "ounces",
              "can", "cans", "egg", "eggs", "stick", "sticks", "bunch",
              "bunches", "sprig", "sprigs", "head", "heads", "package",
              "packages", "piece", "pieces", "handful", "quart", "quarts",
              "pint", "pints", "gallon", "gallons", "fl", "floz", "fl-oz")


def scale_ingredient(text, factor, style="fractions", units="original"):
    """Scale one ingredient line, leaving the unparsable tail intact.

    The leading amount may be '2', '1 1/2', '0.5' and may be followed by a
    unit word ('cups', 'tbsp', 'g', 'pinch', ...). The unit is folded into
    the parsed quantity so conversion and pluralization can act on it; the
    rest of the line (the ingredient name) is preserved verbatim.
    """
    match = re.match(r"^\s*(?P<amount>\S+(?:\s+\d+/\d+)?)\s+(?P<rest>.+)$", text)
    if not match:
        return text
    amount_text, rest = match.group("amount"), match.group("rest")

    value, unit = None, ""
    # try "amount unit" first, so '2 cups' is a volume, not a bare count
    first_word = rest.split(" ", 1)[0]
    if first_word.lower().strip(",") in UNIT_WORDS:
        try:
            value, unit = parse_quantity(f"{amount_text} {first_word}")
            rest = rest.split(" ", 1)[1] if " " in rest else ""
        except ParseError:
            value = None
    if value is None:
        try:
            value, unit = parse_quantity(amount_text)
        except ParseError:
            return text

    scaled = scale_value(value, unit, factor, style=style, units=units)
    return f"{scaled} {rest}".rstrip()


def scale_temperature(text, factor):
    """Scale oven temperatures by the same factor (and the usual 1.8/0.8)."""
    def replace(match):
        value = int(match.group("value"))
        unit = match.group("unit").upper()
        ratio = float(factor)
        if unit == "C":
            return f"{int(round(value * ratio / 5.0) * 5)} C"
        # Fahrenheit recipes are scaled by 1.8 up and 0.8 down
        if ratio >= 1:
            new_value = value * 1.8 * ratio
        else:
            new_value = value * 0.8 * ratio
        return f"{int(round(new_value / 5.0) * 5)} F"

    return TEMPERATURE_RE.sub(replace, text)


def scale_recipe(recipe, factor, style="fractions", units="original",
                 scale_baking=False):
    """Return a new Recipe with every ingredient and temperature scaled."""
    ingredients = [
        scale_ingredient(line, factor, style=style, units=units)
        for line in recipe.ingredients
    ]
    steps = [
        scale_temperature(scale_ingredient(line, factor, style=style, units=units)
                          if line[:1].isdigit() else line, factor)
        if (scale_baking and TEMPERATURE_RE.search(line)) else line
        for line in recipe.steps
    ]
    title = recipe.title
    if title.lower().endswith("serves " + str(recipe.servings or "")):
        target = int(Fraction(recipe.servings) * Fraction(factor).limit_denominator(10000))
        title = f"{title[:title.lower().rfind('serves')].strip()} serves {target}"
    return Recipe(title, None, ingredients, steps, list(recipe.notes))


def render_markdown(recipe):
    """Write a recipe back out as markdown."""
    lines = [f"# {recipe.title}", ""]
    if recipe.ingredients:
        lines.append("## Ingredients")
        lines.append("")
        for item in recipe.ingredients:
            lines.append(f"- {item}")
        lines.append("")
    if recipe.steps:
        lines.append("## Instructions")
        lines.append("")
        for index, step in enumerate(recipe.steps, start=1):
            lines.append(f"{index}. {step}")
        lines.append("")
    if recipe.notes:
        lines.append("## Notes")
        lines.append("")
        for note in recipe.notes:
            lines.append(f"- {note}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def format_plain(recipe):
    """A compact plain-text rendering, scaled amounts only."""
    lines = [recipe.title, ""]
    for item in recipe.ingredients:
        lines.append(f"  {item}")
    return "\n".join(lines) + "\n"
