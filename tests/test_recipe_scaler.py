import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from fractions import Fraction

from recipe_scaler import (ParseError, convert, convert_temperature,
                           format_plain, format_quantity, parse_quantity,
                           parse_recipe, practical_round, render_markdown,
                           scale_ingredient, scale_recipe, scale_value)
from recipe_scaler.cli import main

RECIPE = """# Pancakes

Serves 4

## Ingredients

- 1 1/2 cups flour
- 2 tbsp sugar
- 250 g milk
- 3 eggs
- 1 pinch salt

## Instructions

1. Mix everything.
2. Bake at 180 C for 20 minutes.

## Notes

- Keeps well for 2 days.
"""


class QuantityParsingTests(unittest.TestCase):
    def test_integers_and_decimals(self):
        self.assertEqual(parse_quantity("3")[0], Fraction(3))
        self.assertEqual(parse_quantity("0.5")[0], Fraction(1, 2))
        self.assertEqual(parse_quantity("2.25")[0], Fraction(9, 4))

    def test_simple_fraction(self):
        self.assertEqual(parse_quantity("1/4")[0], Fraction(1, 4))

    def test_mixed_number(self):
        self.assertEqual(parse_quantity("1 1/2")[0], Fraction(3, 2))
        self.assertEqual(parse_quantity("2 3/4")[0], Fraction(11, 4))

    def test_units_are_canonicalised(self):
        self.assertEqual(parse_quantity("2 cups")[1], "cup")
        self.assertEqual(parse_quantity("3 tablespoons")[1], "tbsp")
        self.assertEqual(parse_quantity("250 g")[1], "g")
        self.assertEqual(parse_quantity("2 lbs")[1], "lb")
        self.assertEqual(parse_quantity("1 l")[1], "l")

    def test_pinch_becomes_eighths(self):
        value, unit = parse_quantity("1 pinch")
        self.assertEqual(unit, "tsp")
        self.assertEqual(value, Fraction(1, 16))

    def test_unknown_units_are_kept(self):
        value, unit = parse_quantity("3 pinches")
        self.assertEqual(value, Fraction(3, 16))
        self.assertEqual(unit, "tsp")

    def test_phrases_are_not_quantities(self):
        # parse_quantity takes a quantity, not a sentence
        with self.assertRaises(ParseError):
            parse_quantity("3 pinches of saffron")

    def test_junk_rejected(self):
        for text in ["", "a lot", "-", "1/0"]:
            with self.assertRaises(ParseError, msg=text):
                parse_quantity(text)


class ConversionTests(unittest.TestCase):
    def test_volume(self):
        self.assertEqual(convert(Fraction(1), "cup", "ml"), Fraction(240))
        self.assertEqual(convert(Fraction(1), "tbsp", "ml"), Fraction(15))
        self.assertEqual(convert(Fraction(1), "tsp", "ml"), Fraction(5))
        self.assertEqual(convert(Fraction(1), "l", "ml"), Fraction(1000))

    def test_mass(self):
        self.assertEqual(convert(Fraction(1), "kg", "g"), Fraction(1000))
        self.assertEqual(convert(Fraction(1), "lb", "g"), Fraction(453592, 1000))

    def test_identity_and_unknown_pairs(self):
        self.assertEqual(convert(Fraction(3), "cup", "cup"), Fraction(3))
        self.assertEqual(convert(Fraction(3), "kg", "ml"), Fraction(3))

    def test_temperature(self):
        self.assertEqual(convert_temperature(Fraction(100), "C", "F"), Fraction(212))
        self.assertEqual(convert_temperature(Fraction(212), "F", "C"), Fraction(100))
        self.assertEqual(convert_temperature(Fraction(180), "C", "C"), Fraction(180))


class FormattingTests(unittest.TestCase):
    def test_fractions(self):
        self.assertEqual(format_quantity(Fraction(3, 2), "cup"), "1 1/2 cups")
        self.assertEqual(format_quantity(Fraction(1, 2), "cup"), "1/2 cups")
        self.assertEqual(format_quantity(Fraction(3), "cups"), "3 cups")

    def test_plural_agreement(self):
        self.assertEqual(format_quantity(Fraction(1), "cup"), "1 cup")
        self.assertEqual(format_quantity(Fraction(2), "cup"), "2 cups")
        self.assertEqual(format_quantity(Fraction(1), "pinch"), "1 pinch")

    def test_mixed_style(self):
        self.assertEqual(format_quantity(Fraction(3, 2), "cup", "mixed"), "1-1/2 cups")

    def test_decimals(self):
        self.assertEqual(format_quantity(Fraction(1, 2), "cup", "decimals"), "0.5 cups")
        self.assertEqual(format_quantity(Fraction(3, 2), "cup", "decimals"), "1.5 cups")

    def test_no_unit(self):
        self.assertEqual(format_quantity(Fraction(3)), "3")

    def test_practical_rounding(self):
        self.assertEqual(practical_round(Fraction(74, 100)), Fraction(3, 4))
        self.assertEqual(practical_round(Fraction(26, 100)), Fraction(1, 4))
        self.assertEqual(practical_round(Fraction(0)), Fraction(0))


class ScalingTests(unittest.TestCase):
    def test_double_and_halve(self):
        self.assertEqual(scale_ingredient("1 1/2 cups flour", 2), "3 cups flour")
        self.assertEqual(scale_ingredient("2 tbsp sugar", Fraction(1, 2)),
                         "1 tbsp sugar")

    def test_counts_stay_whole(self):
        self.assertEqual(scale_ingredient("3 eggs", 2), "6 eggs")
        # half of three eggs is two, not one and a half
        self.assertEqual(scale_ingredient("3 eggs", Fraction(1, 2)), "2 eggs")

    def test_pinch_scaling(self):
        self.assertEqual(scale_ingredient("1 pinch salt", 2), "1/8 tsp salt")

    def test_mass_scaling_and_conversion(self):
        self.assertEqual(scale_ingredient("250 g milk", 2), "500 g milk")
        # halving stays in kilograms unless metric output is asked for
        self.assertEqual(scale_ingredient("1 kg flour", Fraction(1, 2)),
                         "1/2 kg flour")
        self.assertEqual(
            scale_ingredient("1 kg flour", Fraction(1, 2), units="metric"),
            "500 g flour")

    def test_volume_conversion_to_metric(self):
        self.assertEqual(scale_ingredient("1 cup water", 1, units="metric"),
                         "240 ml water")

    def test_unparsable_lines_pass_through(self):
        self.assertEqual(scale_ingredient("salt to taste", 2), "salt to taste")
        self.assertEqual(scale_ingredient("", 2), "")

    def test_tiny_amounts_are_not_erased(self):
        scaled = scale_value(Fraction(1, 32), "tsp", 1, style="decimals")
        self.assertNotEqual(scaled, "0 tsp")


class RecipeTests(unittest.TestCase):
    def setUp(self):
        self.recipe = parse_recipe(RECIPE)

    def test_title_and_servings(self):
        self.assertEqual(self.recipe.title, "Pancakes")
        self.assertEqual(self.recipe.servings, 4)

    def test_ingredients_collected(self):
        self.assertEqual(len(self.recipe.ingredients), 5)
        self.assertEqual(self.recipe.ingredients[0], "1 1/2 cups flour")

    def test_steps_lose_their_numbering(self):
        self.assertEqual(self.recipe.steps[0], "Mix everything.")

    def test_notes_collected(self):
        self.assertEqual(len(self.recipe.notes), 1)

    def test_factor_for_servings(self):
        self.assertEqual(self.recipe.factor_for_servings(8), Fraction(2))
        self.assertEqual(self.recipe.factor_for_servings(2), Fraction(1, 2))

    def test_factor_without_servings(self):
        recipe = parse_recipe("# X\n\n- 1 cup flour\n")
        with self.assertRaises(ValueError):
            recipe.factor_for_servings(4)

    def test_scaling_the_whole_recipe(self):
        doubled = scale_recipe(self.recipe, 2)
        self.assertEqual(doubled.ingredients[0], "3 cups flour")
        self.assertEqual(len(doubled.steps), 2)

    def test_temperatures_stay_put_by_default(self):
        doubled = scale_recipe(self.recipe, 2)
        self.assertIn("180 C", doubled.steps[1])

    def test_temperatures_scale_on_request(self):
        doubled = scale_recipe(self.recipe, 2, scale_baking=True)
        self.assertIn("360 C", doubled.steps[1])

    def test_markdown_rendering(self):
        text = render_markdown(scale_recipe(self.recipe, 2))
        self.assertIn("# Pancakes", text)
        self.assertIn("## Ingredients", text)
        self.assertIn("- 3 cups flour", text)
        self.assertIn("1. Mix everything.", text)
        self.assertIn("- Keeps well for 2 days.", text)

    def test_plain_rendering(self):
        text = format_plain(scale_recipe(self.recipe, 2))
        self.assertIn("Pancakes", text)
        self.assertNotIn("##", text)


class CliTests(unittest.TestCase):
    def run_main(self, argv, stdin=None):
        out, err = io.StringIO(), io.StringIO()
        import sys
        old = sys.stdin
        if stdin is not None:
            import io as _io
            sys.stdin = _io.StringIO(stdin)
        try:
            with redirect_stdout(out), redirect_stderr(err):
                code = main(argv)
        finally:
            sys.stdin = old
        return code, out.getvalue(), err.getvalue()

    def test_factor_from_stdin(self):
        code, out, _ = self.run_main(["-", "--factor", "2"], stdin=RECIPE)
        self.assertEqual(code, 0)
        self.assertIn("- 3 cups flour", out)

    def test_servings_from_stdin(self):
        code, out, _ = self.run_main(["-", "--servings", "8"], stdin=RECIPE)
        self.assertEqual(code, 0)
        self.assertIn("- 3 cups flour", out)

    def test_json_output(self):
        import json
        code, out, _ = self.run_main(["-", "--factor", "2", "--json"], stdin=RECIPE)
        payload = json.loads(out)
        self.assertEqual(payload["factor"], "2")
        self.assertEqual(payload["ingredients"][0], "3 cups flour")

    def test_plain_output(self):
        code, out, _ = self.run_main(["-", "--factor", "2", "--plain"], stdin=RECIPE)
        self.assertNotIn("##", out)
        self.assertIn("3 cups flour", out)

    def test_missing_factor_is_usage_error(self):
        code, _, err = self.run_main(["-"], stdin=RECIPE)
        self.assertEqual(code, 2)
        self.assertIn("usage", err)

    def test_both_factors_rejected(self):
        code, _, err = self.run_main(["-", "--factor", "2", "--servings", "8"],
                                     stdin=RECIPE)
        self.assertEqual(code, 2)
        self.assertIn("not both", err)

    def test_empty_input(self):
        code, _, err = self.run_main(["-", "--factor", "2"], stdin="   ")
        self.assertEqual(code, 1)
        self.assertIn("empty", err)

    def test_missing_file(self):
        code, _, err = self.run_main(["/nope/recipe.md", "--factor", "2"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
