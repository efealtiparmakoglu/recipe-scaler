"""recipe-scaler — scale recipe quantities with exact fraction arithmetic."""
__version__ = "1.0.0"

from .scaling import (Recipe, format_plain, parse_recipe, render_markdown,
                      scale_ingredient, scale_recipe, scale_temperature)
from .units import (ParseError, convert, convert_temperature, format_quantity,
                    parse_quantity, practical_round, scale_value)

__all__ = [
    "__version__", "Recipe", "parse_recipe", "scale_recipe", "scale_ingredient",
    "scale_temperature", "render_markdown", "format_plain", "parse_quantity",
    "format_quantity", "convert", "convert_temperature", "practical_round",
    "scale_value", "ParseError",
]
