"""Scoring: what makes one suggestion better than another.

Everything is expressed in "penalty points", loosely calibrated so that one
point is about as bad as being one kcal off target. Lower is better.

The weights below are not internal tuning knobs -- they are the user-facing
settings from the concept doc, in their raw form. "How precisely must the
budget be hit", "may I go over", "how many ingredients at most" are all just
different weights on the same function.

The score splits into two halves, and the split is what makes the search fast:

  * `portion_cost` depends only on the portion itself -- packaging waste,
    repetition, the price of another item on the plate. It can be computed
    once per portion and then carried as a running sum.
  * `fit_cost` depends only on the totals -- how far the plate lands from the
    budget. It is a handful of float operations.

`score` composes both and is the readable reference; the search calls the two
halves directly. A test pins them to each other.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .model import Budget, Nutrition, Portion


@dataclass(frozen=True)
class Weights:
    # Missing the calorie target, per kcal. Overshooting costs more than
    # undershooting, because eating too much undoes the day while eating a
    # little too little does not.
    kcal_under: float = 1.0
    kcal_over: float = 2.5

    # Missing a macro target, per gram. Protein is asymmetric: falling short
    # is the failure people actually care about, exceeding it rarely matters.
    protein_under: float = 9.0
    protein_over: float = 1.0
    carbs: float = 1.0
    fat: float = 2.5

    # Per gram left standing open in the fridge afterwards. This is the rule
    # that makes whole tins win: half a tin of sweetcorn leaves 75 g behind
    # and pays for it, a whole tin leaves nothing and pays nothing.
    offcut: float = 0.35

    # Flat reward for using up a pack that is already open.
    use_up_bonus: float = 60.0

    # Per recent use of the same product, so the same dinner does not come
    # back five evenings running.
    repetition: float = 25.0

    # Per item on the plate. Three ingredients beat six even at equal accuracy.
    component: float = 20.0


DEFAULT_WEIGHTS = Weights()


# --------------------------------------------------------------------------
# The two halves
# --------------------------------------------------------------------------


def kcal_cost(kcal: float, budget: Budget, w: Weights) -> float:
    diff = kcal - budget.kcal
    return diff * w.kcal_over if diff > 0 else -diff * w.kcal_under


def macro_cost(
    carbs: float, protein: float, fat: float, budget: Budget, w: Weights
) -> float:
    cost = 0.0

    if budget.protein_g is not None:
        diff = protein - budget.protein_g
        cost += -diff * w.protein_under if diff < 0 else diff * w.protein_over

    if budget.carbs_g is not None:
        cost += abs(carbs - budget.carbs_g) * w.carbs

    if budget.fat_g is not None:
        cost += abs(fat - budget.fat_g) * w.fat

    return cost


def fit_cost(
    kcal: float, carbs: float, protein: float, fat: float, budget: Budget, w: Weights
) -> float:
    """How badly the plate misses the budget. Depends only on the totals."""
    return kcal_cost(kcal, budget, w) + macro_cost(carbs, protein, fat, budget, w)


def packaging_cost(portion: Portion, w: Weights) -> float:
    packaging = portion.packaging
    cost = packaging.leftover_g * w.offcut
    if packaging.finishes_open_pack:
        cost -= w.use_up_bonus
    return cost


def portion_cost(
    portion: Portion, w: Weights, history: Mapping[str, int] | None = None
) -> float:
    """Cost of putting this portion on the plate, whatever else is on it."""
    uses = (history or {}).get(portion.product.id, 0)
    return packaging_cost(portion, w) + uses * w.repetition + w.component


# --------------------------------------------------------------------------
# Composition
# --------------------------------------------------------------------------


def totals_of(portions: Sequence[Portion]) -> Nutrition:
    total = Nutrition()
    for portion in portions:
        total = total + portion.nutrition
    return total


def score(
    portions: Sequence[Portion],
    budget: Budget,
    weights: Weights = DEFAULT_WEIGHTS,
    history: Mapping[str, int] | None = None,
    totals: Nutrition | None = None,
) -> tuple[float, dict[str, float]]:
    """Score a combination. Returns the total and a per-term breakdown.

    `history` maps a product id to how often it was used in the recent window.
    `totals` may be passed in when the caller already has them.
    """
    history = history or {}
    if totals is None:
        totals = totals_of(portions)

    breakdown = {
        "kcal": kcal_cost(totals.kcal, budget, weights),
        "macros": macro_cost(
            totals.carbs_g, totals.protein_g, totals.fat_g, budget, weights
        ),
        "packaging": sum(packaging_cost(p, weights) for p in portions),
        "repetition": sum(
            history.get(p.product.id, 0) * weights.repetition for p in portions
        ),
        "components": len(portions) * weights.component,
    }
    return sum(breakdown.values()), breakdown
