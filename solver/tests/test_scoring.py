"""The score function: does it actually prefer what the product promises?"""

from __future__ import annotations

import pytest

from conftest import make_product
from whatfits import Budget, PackGrid, Weights, score
from whatfits.scoring import DEFAULT_WEIGHTS, fit_cost, portion_cost

W = DEFAULT_WEIGHTS


def _score(portions, budget, history=None) -> float:
    return score(portions, budget, W, history)[0]


# --------------------------------------------------------------------------
# The rule the whole product rests on
# --------------------------------------------------------------------------


# Symmetric calorie weights, so that accuracy genuinely ties and packaging is
# left to decide. The default weights are deliberately asymmetric.
EVEN = Weights(kcal_under=1.0, kcal_over=1.0)


def test_whole_tin_beats_half_tin_when_accuracy_ties():
    """The central promise: do not break into a tin to use part of it."""
    product = make_product(
        "corn", kcal=100, grid=PackGrid(pack_g=100, unit="tin", fraction=0.5, max_packs=2)
    )
    half, whole = product.portions()[0], product.portions()[1]

    # 75 kcal sits exactly between 50 and 100, so both miss by the same amount.
    budget = Budget(kcal=75)
    assert score((whole,), budget, EVEN)[0] < score((half,), budget, EVEN)[0]


def test_accuracy_outranks_packaging_at_default_weights():
    """The trade-off, stated explicitly so a change to it cannot pass unnoticed.

    Going 25 kcal over budget costs more than leaving 50 g of a tin open. That
    is a judgement call, not a law: it is the balance between `kcal_over` and
    `offcut`, and it is exactly what phase 1 should tune against real use.
    """
    product = make_product(
        "corn", kcal=100, grid=PackGrid(pack_g=100, unit="tin", fraction=0.5, max_packs=2)
    )
    half, whole = product.portions()[0], product.portions()[1]

    budget = Budget(kcal=75)
    assert _score((half,), budget) < _score((whole,), budget)


def test_using_up_an_open_pack_is_rewarded():
    fresh = make_product("beans", grid=PackGrid(pack_g=100, fraction=0.5, max_packs=2))
    opened = make_product(
        "beans", grid=PackGrid(pack_g=100, fraction=0.5, max_packs=2), open_g=50
    )
    budget = Budget(kcal=50)

    from_fresh = fresh.portions()[0]
    from_open = opened.portions()[0]
    assert from_fresh.grams == from_open.grams
    assert _score((from_open,), budget) < _score((from_fresh,), budget)


# --------------------------------------------------------------------------
# Asymmetries
# --------------------------------------------------------------------------


def test_going_over_costs_more_than_going_under():
    product = make_product("thing", kcal=100)
    portions = {p.grams: p for p in product.portions()}
    budget = Budget(kcal=50)  # 50 g hits it exactly

    over = _score((portions[60],), budget)
    under = _score((portions[40],), budget)
    assert over > under


def test_falling_short_on_protein_costs_more_than_exceeding_it():
    lean = make_product("lean", kcal=100, carbs=0, protein=20, fat=0)
    portions = {p.grams: p for p in lean.portions()}
    budget = Budget(kcal=100, protein_g=20)  # 100 g hits both exactly

    short = _score((portions[80],), budget)
    plenty = _score((portions[100],), budget)
    assert short > plenty


def test_repetition_is_penalised():
    product = make_product("rice")
    portion = product.portions()[0]
    budget = Budget(kcal=portion.nutrition.kcal)

    assert _score((portion,), budget, {"rice": 3}) > _score((portion,), budget)


def test_fewer_components_win_at_equal_accuracy():
    one = make_product("a", kcal=100)
    two = make_product("b", kcal=100)
    budget = Budget(kcal=100)

    single = [p for p in one.portions() if p.grams == 100][0]
    halves = (
        [p for p in one.portions() if p.grams == 50][0],
        [p for p in two.portions() if p.grams == 50][0],
    )
    assert _score((single,), budget) < _score(halves, budget)


# --------------------------------------------------------------------------
# The invariant that lets the search take a shortcut
# --------------------------------------------------------------------------


def test_score_equals_the_split_the_search_relies_on():
    """`score` and the two halves the search calls must never drift apart."""
    products = [
        make_product("a", kcal=120, grid=PackGrid(pack_g=80, fraction=0.5), open_g=40),
        make_product("b", kcal=90),
        make_product("c", kcal=300),
    ]
    portions = tuple(p.portions()[1] for p in products)
    budget = Budget(kcal=500, protein_g=40, carbs_g=50, fat_g=15)
    history = {"b": 2}

    totals = portions[0].nutrition
    for portion in portions[1:]:
        totals = totals + portion.nutrition

    composed = sum(portion_cost(p, W, history) for p in portions) + fit_cost(
        totals.kcal, totals.carbs_g, totals.protein_g, totals.fat_g, budget, W
    )
    assert _score(portions, budget, history) == pytest.approx(composed)


def test_breakdown_sums_to_the_score():
    product = make_product("x")
    portions = (product.portions()[2],)
    budget = Budget(kcal=200, protein_g=20)
    total, breakdown = score(portions, budget, W)
    assert sum(breakdown.values()) == pytest.approx(total)


def test_weights_are_the_user_settings():
    """Turning the overshoot weight up must make overshooting less attractive."""
    product = make_product("thing", kcal=100)
    over = [p for p in product.portions() if p.grams == 70][0]
    budget = Budget(kcal=50)

    relaxed = score((over,), budget, Weights(kcal_over=0.5))[0]
    strict = score((over,), budget, Weights(kcal_over=10.0))[0]
    assert strict > relaxed
