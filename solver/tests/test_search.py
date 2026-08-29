"""The search: correctness of the pruning, and the guarantees it must keep."""

from __future__ import annotations

import itertools

import pytest

from conftest import make_product
from whatfits import Budget, MassGrid, Meal, PackGrid, Weights, load_pantry, score, solve
from whatfits.scoring import DEFAULT_WEIGHTS

W = DEFAULT_WEIGHTS


# --------------------------------------------------------------------------
# The guarantee the product is built on
# --------------------------------------------------------------------------


def test_every_suggested_amount_sits_on_the_grid():
    """Nothing may come back that a person cannot serve. No 37 g of sweetcorn."""
    pantry = [
        make_product("corn", kcal=80, grid=PackGrid(pack_g=150, unit="tin", fraction=0.5)),
        make_product("rice", kcal=349, grid=MassGrid(step_g=10, min_g=40, max_g=150)),
        make_product("chicken", kcal=106, grid=PackGrid(pack_g=150, unit="breast")),
    ]
    allowed = {p.id: {portion.grams for portion in p.portions()} for p in pantry}

    result = solve(pantry, Budget(kcal=700, protein_g=40), top_k=10)
    assert result.suggestions

    for suggestion in result.suggestions:
        for portion in suggestion.portions:
            assert portion.grams in allowed[portion.product.id]


def test_a_whole_tin_is_preferred_when_accuracy_ties():
    """With symmetric calorie weights, packaging decides -- and picks the tin."""
    pantry = [
        make_product("corn", kcal=100, grid=PackGrid(pack_g=100, unit="tin", fraction=0.5))
    ]
    even = Weights(kcal_under=1.0, kcal_over=1.0)
    budget = Budget(kcal=75, max_under_kcal=50, max_over_kcal=50)
    best = solve(pantry, budget, weights=even).suggestions[0]
    assert best.portions[0].grams == 100


# --------------------------------------------------------------------------
# Pruning must not lose the optimum
# --------------------------------------------------------------------------


def _brute_force(pantry, budget, max_components):
    """Every legal combination, scored, no pruning at all."""
    portions_by_product = [p.portions() for p in pantry]
    best = None

    for size in range(1, max_components + 1):
        for chosen_products in itertools.combinations(range(len(pantry)), size):
            options = [portions_by_product[i] for i in chosen_products]
            for combination in itertools.product(*options):
                kcal = sum(p.nutrition.kcal for p in combination)
                if not budget.accepts(kcal):
                    continue
                value = score(combination, budget, W)[0]
                if best is None or value < best:
                    best = value
    return best


@pytest.mark.parametrize("kcal", [250, 400, 620, 900])
def test_branch_and_bound_finds_the_same_optimum_as_brute_force(kcal):
    pantry = [
        make_product("a", kcal=120, carbs=20, protein=5, fat=2,
                     grid=PackGrid(pack_g=80, unit="tin", fraction=0.5, max_packs=2)),
        make_product("b", kcal=349, carbs=78, protein=7, fat=1,
                     grid=MassGrid(step_g=20, min_g=40, max_g=140)),
        make_product("c", kcal=106, carbs=0, protein=23, fat=2,
                     grid=PackGrid(pack_g=150, unit="breast", max_packs=2)),
        make_product("d", kcal=587, carbs=16, protein=26, fat=49,
                     grid=MassGrid(step_g=10, min_g=10, max_g=50)),
    ]
    budget = Budget(kcal=kcal, protein_g=kcal * 0.3 / 4, carbs_g=kcal * 0.45 / 4)

    expected = _brute_force(pantry, budget, max_components=3)
    result = solve(pantry, budget, max_components=3, top_k=1)

    if expected is None:
        assert not result.suggestions
    else:
        assert result.suggestions
        assert result.suggestions[0].score == pytest.approx(expected)


# --------------------------------------------------------------------------
# Constraints
# --------------------------------------------------------------------------


def test_component_limit_is_respected():
    # Each product tops out at 100 kcal, so 180 is reachable with two items.
    pantry = [make_product(f"p{i}", kcal=100) for i in range(6)]
    result = solve(pantry, Budget(kcal=180), max_components=2, top_k=10)
    assert result.suggestions
    assert all(len(s.portions) <= 2 for s in result.suggestions)


def test_results_stay_inside_the_calorie_window():
    pantry = [make_product(f"p{i}", kcal=100 + 40 * i) for i in range(5)]
    budget = Budget(kcal=500, max_over_kcal=20, max_under_kcal=30)
    result = solve(pantry, budget, top_k=10)
    assert result.suggestions
    for suggestion in result.suggestions:
        assert 470 <= suggestion.totals.kcal <= 520


def test_meal_filter_excludes_unsuitable_food():
    breakfast_only = make_product("cereal", meals=frozenset({Meal.BREAKFAST}))
    dinner_only = make_product("chicken", meals=frozenset({Meal.DINNER}))
    result = solve([breakfast_only, dinner_only], Budget(kcal=100), Meal.DINNER, top_k=10)
    used = {p.product.id for s in result.suggestions for p in s.portions}
    assert used == {"chicken"}


def test_suggestions_are_distinct_meals():
    pantry = [make_product(f"p{i}", kcal=100 + 30 * i) for i in range(5)]
    result = solve(pantry, Budget(kcal=400), top_k=5)
    sets = [s.product_ids for s in result.suggestions]
    assert len(sets) == len(set(sets))


def test_suggestions_come_back_best_first():
    pantry = [make_product(f"p{i}", kcal=100 + 30 * i) for i in range(5)]
    result = solve(pantry, Budget(kcal=400), top_k=5)
    scores = [s.score for s in result.suggestions]
    assert scores == sorted(scores)


def test_impossible_budget_returns_nothing_rather_than_nonsense():
    pantry = [make_product("tiny", kcal=10, grid=MassGrid(step_g=10, min_g=10, max_g=20))]
    result = solve(pantry, Budget(kcal=5000, max_under_kcal=100), top_k=5)
    assert result.suggestions == []


def test_reported_totals_match_the_portions():
    pantry = [make_product(f"p{i}", kcal=100 + 30 * i) for i in range(4)]
    result = solve(pantry, Budget(kcal=400, protein_g=30), top_k=3)
    for suggestion in result.suggestions:
        expected = sum(p.nutrition.kcal for p in suggestion.portions)
        assert suggestion.totals.kcal == pytest.approx(expected)


# --------------------------------------------------------------------------
# Against the real pantry
# --------------------------------------------------------------------------


def test_the_shipped_pantry_can_plan_a_normal_evening(pantry_file):
    pantry = load_pantry(pantry_file)
    budget = Budget(kcal=950, protein_g=65, carbs_g=130, fat_g=25)
    result = solve(pantry, budget, Meal.DINNER, top_k=3)

    assert len(result.suggestions) == 3
    assert not result.truncated
    for suggestion in result.suggestions:
        assert budget.accepts(suggestion.totals.kcal)
