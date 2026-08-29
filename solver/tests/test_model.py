"""Nutrition arithmetic, the plausibility check, and the portion grids."""

from __future__ import annotations

import pytest

from conftest import make_product
from whatfits import MassGrid, Nutrition, PackGrid, plausibility_problems


# --------------------------------------------------------------------------
# Nutrition
# --------------------------------------------------------------------------


def test_scaled_is_per_100g():
    per_100g = Nutrition(kcal=200, carbs_g=10, protein_g=5, fat_g=1)
    half = per_100g.scaled(50)
    assert half.kcal == pytest.approx(100)
    assert half.carbs_g == pytest.approx(5)


def test_nutrition_adds_componentwise():
    total = Nutrition(100, 10, 5, 1) + Nutrition(50, 2, 3, 4)
    assert (total.kcal, total.carbs_g, total.protein_g, total.fat_g) == (150, 12, 8, 5)


def test_atwater_uses_4_4_9():
    assert Nutrition(carbs_g=10, protein_g=10, fat_g=10).atwater_kcal == pytest.approx(170)


# --------------------------------------------------------------------------
# Plausibility -- the checks the concept doc asks for
# --------------------------------------------------------------------------


def test_realistic_entry_passes():
    rice = Nutrition(kcal=349, carbs_g=78, protein_g=7, fat_g=0.6)
    assert plausibility_problems(rice) == []


def test_decimal_place_typo_is_caught():
    """500 g of rice is ~600 kcal, not 6000. Per 100 g that is 1200."""
    problems = plausibility_problems(Nutrition(kcal=1200, carbs_g=78, protein_g=7, fat_g=0.6))
    assert any("exceeds pure fat" in p for p in problems)


def test_macros_disagreeing_with_energy_are_caught():
    # Macros imply ~170 kcal, the entry claims 400.
    problems = plausibility_problems(Nutrition(kcal=400, carbs_g=10, protein_g=10, fat_g=10))
    assert any("macros imply" in p for p in problems)


def test_macros_heavier_than_the_food_are_caught():
    problems = plausibility_problems(Nutrition(kcal=500, carbs_g=60, protein_g=30, fat_g=40))
    assert any("more than the food weighs" in p for p in problems)


def test_negative_values_are_caught():
    problems = plausibility_problems(Nutrition(kcal=100, carbs_g=-5, protein_g=10, fat_g=2))
    assert any("negative" in p for p in problems)


def test_fibre_rich_food_is_tolerated():
    """Tinned vegetables legitimately sit above their Atwater estimate."""
    peas = Nutrition(kcal=50, carbs_g=8, protein_g=2.5, fat_g=0.4)
    assert plausibility_problems(peas) == []


# --------------------------------------------------------------------------
# Portion grids
# --------------------------------------------------------------------------


def test_whole_pack_grid_offers_only_whole_packs():
    grid = PackGrid(pack_g=150, unit="tin", fraction=1.0, max_packs=2)
    assert [grams for grams, _ in grid.portions()] == [150, 300]


def test_half_pack_grid_offers_halves():
    grid = PackGrid(pack_g=100, unit="tin", fraction=0.5, max_packs=2)
    assert [grams for grams, _ in grid.portions()] == [50, 100, 150, 200]


def test_pack_labels_read_like_a_kitchen():
    grid = PackGrid(pack_g=100, unit="tin", fraction=0.5, max_packs=2)
    labels = [label for _, label in grid.portions()]
    assert labels[0].startswith("1/2 tin")
    assert labels[1].startswith("1 tin")
    assert labels[2].startswith("1 1/2 tins")


def test_mass_grid_walks_in_steps():
    grid = MassGrid(step_g=10, min_g=40, max_g=70)
    assert [grams for grams, _ in grid.portions()] == [40, 50, 60, 70]


# --------------------------------------------------------------------------
# Packaging consequences
# --------------------------------------------------------------------------


def test_whole_pack_leaves_nothing_open():
    product = make_product(grid=PackGrid(pack_g=100, fraction=1.0, max_packs=2))
    whole = product.portions()[0]
    assert whole.grams == 100
    assert whole.packaging.leftover_g == 0
    assert not whole.packaging.finishes_open_pack


def test_half_pack_leaves_the_other_half_open():
    product = make_product(grid=PackGrid(pack_g=100, fraction=0.5, max_packs=2))
    half = product.portions()[0]
    assert half.grams == 50
    assert half.packaging.leftover_g == pytest.approx(50)


def test_serving_exactly_the_open_amount_finishes_it():
    product = make_product(
        grid=PackGrid(pack_g=100, fraction=0.5, max_packs=2), open_g=50
    )
    half = product.portions()[0]
    assert half.grams == 50
    assert half.packaging.finishes_open_pack
    assert half.packaging.leftover_g == 0
    assert not half.packaging.opens_new_pack


def test_serving_more_than_is_open_finishes_it_and_breaks_into_a_new_pack():
    product = make_product(
        grid=PackGrid(pack_g=100, fraction=0.5, max_packs=2), open_g=50
    )
    # 100 g = the open 50 g, plus 50 g out of a fresh tin.
    full = product.portions()[1]
    assert full.grams == 100
    assert full.packaging.finishes_open_pack
    assert full.packaging.opens_new_pack
    assert full.packaging.leftover_g == pytest.approx(50)


def test_mass_products_never_leave_a_pack_open():
    product = make_product(grid=MassGrid(step_g=5, min_g=5, max_g=50))
    assert all(p.packaging.leftover_g == 0 for p in product.portions())
