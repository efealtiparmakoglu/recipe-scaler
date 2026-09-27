"""recipe-scaler CLI."""
import argparse
import json
import sys
from fractions import Fraction

from . import __version__
from .scaling import format_plain, parse_recipe, render_markdown, scale_recipe
from .units import ParseError

USAGE = f"""recipe-scaler {__version__} — scale recipes, keeping the fractions honest

usage:
  recipe-scaler [recipe.md] [--factor 2 | --servings N] [options]
  cat recipe.md | recipe-scaler --factor 0.5
  recipe-scaler -h | --help

options:
  --factor F        multiply every amount by F (fractions allowed: 3/2)
  --servings N      scale to N servings (needs a serving count in the recipe)
  --style STYLE     fractions (default) | decimals | mixed
  --units UNITS     original (default) | metric | us
  --plain           plain-text output instead of markdown
  --json            machine-readable output
  --scale-temp      also scale oven temperatures (1.8 up, 0.8 down)

exactly one of --factor / --servings is required
exit codes: 0 ok, 1 runtime error, 2 usage error
"""


def build_parser():
    parser = argparse.ArgumentParser(prog="recipe-scaler", add_help=False)
    parser.add_argument("recipe", nargs="?", help="recipe file ('-' for stdin)")
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("--version", action="version", version=f"recipe-scaler {__version__}")
    parser.add_argument("--factor")
    parser.add_argument("--servings", type=int)
    parser.add_argument("--style", choices=["fractions", "decimals", "mixed"],
                        default="fractions")
    parser.add_argument("--units", choices=["original", "metric", "us"],
                        default="original")
    parser.add_argument("--plain", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--scale-temp", action="store_true",
                        help="also scale oven temperatures (1.8/0.8 rule)")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.help or not (args.factor or args.servings):
        print(USAGE, file=sys.stderr)
        return 2
    if args.factor and args.servings:
        print("recipe-scaler: use --factor or --servings, not both", file=sys.stderr)
        return 2

    try:
        if args.recipe in (None, "-"):
            text = sys.stdin.read()
        else:
            with open(args.recipe, "r", encoding="utf-8") as handle:
                text = handle.read()
    except OSError as exc:
        print(f"recipe-scaler: {exc}", file=sys.stderr)
        return 1

    if not text.strip():
        print("recipe-scaler: the recipe is empty", file=sys.stderr)
        return 1

    try:
        recipe = parse_recipe(text)
        if args.servings:
            factor = recipe.factor_for_servings(args.servings)
        else:
            factor = Fraction(args.factor)
        scaled = scale_recipe(recipe, factor, style=args.style, units=args.units,
                              scale_baking=args.scale_temp)
    except (ParseError, ValueError) as exc:
        print(f"recipe-scaler: {exc}", file=sys.stderr)
        return 1

    if args.json:
        payload = {
            "title": scaled.title,
            "factor": str(factor),
            "ingredients": scaled.ingredients,
            "steps": scaled.steps,
            "notes": scaled.notes,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if args.plain:
        sys.stdout.write(format_plain(scaled))
    else:
        sys.stdout.write(render_markdown(scaled))
    return 0


if __name__ == "__main__":
    sys.exit(main())
