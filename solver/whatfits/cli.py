"""Command line interface for the phase 0 prototype.

    python -m whatfits plan 950 --protein 65 --carbs 130 --fat 25
    python -m whatfits check
    python -m whatfits benchmark --runs 300
"""

from __future__ import annotations

import argparse
import random
import statistics
from pathlib import Path
from typing import Sequence

from .model import Budget, Meal, Product, Suggestion
from .pantry import PantryError, check_pantry, load_pantry
from .search import solve

DEFAULT_PANTRY = Path(__file__).resolve().parent.parent / "data" / "pantry.json"


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------


def _format_suggestion(index: int, suggestion: Suggestion, budget: Budget) -> str:
    totals = suggestion.totals
    lines = [
        f"{index:>2}.  {totals.kcal:>4.0f} kcal      "
        f"(target {budget.kcal:.0f}, {totals.kcal - budget.kcal:+.0f})"
        f"      score {suggestion.score:.0f}"
    ]

    width = max(len(p.label) for p in suggestion.portions)
    for portion in sorted(suggestion.portions, key=lambda p: -p.nutrition.kcal):
        packaging = portion.packaging
        if packaging.finishes_open_pack and packaging.opens_new_pack:
            note = (
                "   <- uses up the open pack, opens a new one"
                f" ({packaging.leftover_g:.0f} g left)"
            )
        elif packaging.finishes_open_pack:
            note = "   <- uses up the pack already open"
        elif packaging.leftover_g > 0:
            note = f"   ({packaging.leftover_g:.0f} g left open)"
        else:
            note = ""
        lines.append(
            f"      {portion.label:<{width}}  {portion.product.name}"
            f"  ~{portion.nutrition.kcal:.0f} kcal{note}"
        )

    macros = []
    for label, actual, target in (
        ("carbs", totals.carbs_g, budget.carbs_g),
        ("protein", totals.protein_g, budget.protein_g),
        ("fat", totals.fat_g, budget.fat_g),
    ):
        if target is None:
            macros.append(f"{label} {actual:.0f} g")
        else:
            macros.append(f"{label} {actual:.0f} g ({actual - target:+.0f})")
    lines.append("      " + "   ".join(macros))

    return "\n".join(lines)


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


def _load(path: Path) -> list[Product]:
    try:
        return load_pantry(path)
    except (PantryError, OSError) as error:
        raise SystemExit(f"could not read pantry: {error}")


def cmd_plan(args: argparse.Namespace) -> int:
    pantry = _load(args.pantry)
    meal = Meal(args.meal) if args.meal else None

    budget = Budget(
        kcal=args.kcal,
        protein_g=args.protein,
        carbs_g=args.carbs,
        fat_g=args.fat,
        max_over_kcal=args.max_over,
        max_under_kcal=args.max_under,
    )

    usable = sum(1 for p in pantry if meal is None or meal in p.meals)
    result = solve(
        pantry,
        budget,
        meal,
        max_components=args.components,
        top_k=args.top,
    )

    targets = [f"{budget.kcal:.0f} kcal"]
    for label, value in (("carbs", args.carbs), ("protein", args.protein), ("fat", args.fat)):
        if value is not None:
            targets.append(f"{value:.0f} g {label}")

    print()
    print("Budget    " + "   ".join(targets))
    print(
        f"Pantry    {len(pantry)} products"
        + (f", {usable} usable for {meal.value}" if meal else "")
    )
    print(
        f"Search    {result.combinations_evaluated:,} combinations"
        f" from {result.nodes_visited:,} nodes"
        f" in {result.elapsed_s * 1000:.0f} ms"
        + ("  (truncated -- node limit reached)" if result.truncated else "")
    )
    print()

    if not result.suggestions:
        print("Nothing in the pantry fits that budget within the given tolerance.")
        print("Try a wider tolerance (--max-under / --max-over) or more components.")
        return 1

    for index, suggestion in enumerate(result.suggestions, start=1):
        print(_format_suggestion(index, suggestion, budget))
        print()

    return 0


def cmd_check(args: argparse.Namespace) -> int:
    pantry = _load(args.pantry)
    problems = check_pantry(pantry)

    print()
    print(f"Checked {len(pantry)} products in {args.pantry}")
    print()

    if not problems:
        print("No problems found. Every entry's macros match its stated energy.")
        return 0

    for product_id, found in problems.items():
        print(f"  {product_id}")
        for problem in found:
            print(f"      - {problem}")
    print()
    print(f"{len(problems)} of {len(pantry)} products need attention.")
    return 1


def cmd_benchmark(args: argparse.Namespace) -> int:
    """The question phase 0 exists to answer.

    Insisting on whole tins and sensible gram steps costs accuracy in
    principle. This measures how much, across a spread of realistic evening
    budgets: how often a suggestion exists at all, how far off it lands, and
    how long the search takes.
    """
    pantry = _load(args.pantry)
    rng = random.Random(args.seed)
    meal = Meal(args.meal) if args.meal else None

    solved = 0
    kcal_errors: list[float] = []
    protein_gaps: list[float] = []
    components: list[int] = []
    timings_ms: list[float] = []
    offcuts: list[float] = []

    for _ in range(args.runs):
        # A realistic evening: what is left after a normal day of eating,
        # with macro targets in roughly conventional proportions.
        kcal = rng.uniform(300, 1200)
        budget = Budget(
            kcal=kcal,
            protein_g=kcal * 0.30 / 4,
            carbs_g=kcal * 0.45 / 4,
            fat_g=kcal * 0.25 / 9,
            max_over_kcal=args.max_over,
            max_under_kcal=args.max_under,
        )

        result = solve(pantry, budget, meal, max_components=args.components, top_k=1)
        timings_ms.append(result.elapsed_s * 1000)

        if not result.suggestions:
            continue

        solved += 1
        best = result.suggestions[0]
        totals = best.totals
        kcal_errors.append(abs(totals.kcal - budget.kcal))
        protein_gaps.append(max(0.0, budget.protein_g - totals.protein_g))
        components.append(len(best.portions))
        offcuts.append(sum(p.packaging.leftover_g for p in best.portions))

    print()
    print(f"Benchmark  {args.runs} random evening budgets, 300-1200 kcal")
    print(f"Pantry     {len(pantry)} products" + (f", meal={meal.value}" if meal else ""))
    print(f"Tolerance  -{args.max_under:.0f} / +{args.max_over:.0f} kcal,"
          f" at most {args.components} components")
    print()

    rate = solved / args.runs if args.runs else 0.0
    print(f"  solved                {solved}/{args.runs}  ({rate:.0%})")

    if kcal_errors:
        ordered = sorted(kcal_errors)
        p90 = ordered[min(len(ordered) - 1, int(0.9 * len(ordered)))]
        print(f"  kcal error  median    {statistics.median(kcal_errors):.0f} kcal")
        print(f"              p90       {p90:.0f} kcal")
        print(f"              worst     {max(kcal_errors):.0f} kcal")
        print(f"  protein short median  {statistics.median(protein_gaps):.1f} g")
        print(f"  components  median    {statistics.median(components):.0f}")
        print(f"  left-over   median    {statistics.median(offcuts):.0f} g per meal")

    print(f"  runtime     median    {statistics.median(timings_ms):.0f} ms")
    print(f"              worst     {max(timings_ms):.0f} ms")
    print()
    return 0


# --------------------------------------------------------------------------
# Argument parsing
# --------------------------------------------------------------------------


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--pantry", type=Path, default=DEFAULT_PANTRY, help="pantry JSON file"
    )
    parser.add_argument(
        "--meal", choices=[m.value for m in Meal], help="restrict to food suited to this meal"
    )
    parser.add_argument("--components", type=int, default=3, help="max items on the plate")
    parser.add_argument("--max-over", type=float, default=50.0, help="kcal allowed over budget")
    parser.add_argument("--max-under", type=float, default=150.0, help="kcal allowed under budget")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="whatfits", description="Plan the last meal of the day from what is left."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="suggest meals for a remaining budget")
    plan.add_argument("kcal", type=float, help="calories left for today")
    plan.add_argument("--protein", type=float, help="protein still to eat, in grams")
    plan.add_argument("--carbs", type=float, help="carbohydrates still to eat, in grams")
    plan.add_argument("--fat", type=float, help="fat still to eat, in grams")
    plan.add_argument("--top", type=int, default=3, help="how many suggestions to show")
    _add_common(plan)
    plan.set_defaults(func=cmd_plan)

    check = sub.add_parser("check", help="run the plausibility check over the pantry")
    check.add_argument("--pantry", type=Path, default=DEFAULT_PANTRY, help="pantry JSON file")
    check.set_defaults(func=cmd_check)

    bench = sub.add_parser("benchmark", help="measure the cost of the portion grid")
    bench.add_argument("--runs", type=int, default=200, help="how many random budgets")
    bench.add_argument("--seed", type=int, default=20260829, help="RNG seed")
    _add_common(bench)
    bench.set_defaults(func=cmd_benchmark)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
