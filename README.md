# recipe-scaler

**Scale recipe quantities with exact fraction arithmetic — unit conversion,
fraction/decimal/mixed output, markdown rendering. Zero dependencies.**

```
$ recipe-scaler pancakes.md --factor 2
# Pancakes

## Ingredients

- 3 cups flour
- 4 tbsp sugar
- 500 g milk
- 6 eggs
- 1/8 tsp salt
- 4 cups water

## Instructions

1. Mix everything.
2. Bake at 180 C for 20 minutes.
```

Doubling a recipe is easy; doubling it *correctly* is not. `1 1/2` has to
become `3` and not `3.0`, half a batch has to stay half, three eggs have
to stay a whole number of eggs, and a pinch has to become an eighth of a
teaspoon instead of vanishing.

## What it does

- **Exact arithmetic** — every amount is a `Fraction`, so nothing
  accumulates rounding error through a dozen lines of scaling.
- **Formats** — `1 1/2` (fractions), `1-1/2` (mixed) or `1.5` (decimals),
  chosen per run; the unit agrees in number with the amount.
- **Units** — US volume and mass, metric, or the original spelling;
  `2 cups` becomes `480 ml` when you ask for metric.
- **Readable scaling** — amounts snap to eighths, quarters and halves;
  countable things (eggs, cloves, cans) stay whole; a rounding step never
  erases an ingredient into `0`.
- **Honest about baking** — oven temperatures do not scale linearly, so
  they stay put unless you pass `--scale-temp`.

## Usage

```sh
recipe-scaler recipe.md --factor 2
recipe-scaler recipe.md --servings 8          # needs a serving count
recipe-scaler recipe.md --factor 1/2 --units metric --style decimals
cat recipe.md | recipe-scaler --factor 0.5 > half.md
```

Exit codes: 0 ok, 1 runtime or parse error, 2 usage error.

## Development

```sh
python3 -m unittest discover -s tests   # 44 tests
```

## License

MIT — see [LICENSE](LICENSE).
