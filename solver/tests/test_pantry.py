"""Loading and validating pantry files."""

from __future__ import annotations

import json

import pytest

from whatfits import Meal, PantryError, check_pantry, load_pantry
from whatfits.model import MassGrid, PackGrid


def test_shipped_pantry_loads(pantry_file):
    pantry = load_pantry(pantry_file)
    assert len(pantry) >= 6
    assert {p.id for p in pantry} >= {"rice-dry", "sweetcorn-tinned", "kidney-beans"}


def test_shipped_pantry_is_plausible(pantry_file):
    """The data we ship must pass the check we impose on users."""
    assert check_pantry(load_pantry(pantry_file)) == {}


def test_grids_are_built_from_their_kind(pantry_file):
    pantry = {p.id: p for p in load_pantry(pantry_file)}
    assert isinstance(pantry["sweetcorn-tinned"].grid, PackGrid)
    assert isinstance(pantry["rice-dry"].grid, MassGrid)


def test_open_pack_is_read(pantry_file):
    pantry = {p.id: p for p in load_pantry(pantry_file)}
    assert pantry["kidney-beans"].open_g > 0


def test_meals_are_parsed(pantry_file):
    pantry = {p.id: p for p in load_pantry(pantry_file)}
    assert Meal.DINNER in pantry["rice-dry"].meals
    assert Meal.BREAKFAST not in pantry["rice-dry"].meals


# --------------------------------------------------------------------------
# Malformed input
# --------------------------------------------------------------------------


def _write(tmp_path, payload):
    path = tmp_path / "pantry.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_missing_products_list_is_rejected(tmp_path):
    with pytest.raises(PantryError, match="products"):
        load_pantry(_write(tmp_path, {"nope": []}))


def test_unknown_grid_kind_is_rejected(tmp_path):
    payload = {
        "products": [
            {
                "id": "x",
                "name": "X",
                "per_100g": {"kcal": 100, "carbs_g": 1, "protein_g": 1, "fat_g": 1},
                "grid": {"kind": "sorcery"},
                "meals": ["dinner"],
            }
        ]
    }
    with pytest.raises(PantryError, match="grid kind"):
        load_pantry(_write(tmp_path, payload))


def test_duplicate_ids_are_rejected(tmp_path):
    entry = {
        "id": "x",
        "name": "X",
        "per_100g": {"kcal": 100, "carbs_g": 1, "protein_g": 1, "fat_g": 1},
        "grid": {"kind": "mass", "step_g": 10, "min_g": 10, "max_g": 50},
        "meals": ["dinner"],
    }
    with pytest.raises(PantryError, match="duplicate"):
        load_pantry(_write(tmp_path, {"products": [entry, dict(entry)]}))


def test_implausible_entry_loads_but_is_reported(tmp_path):
    """Bad data is a warning, not a parse error -- the user decides."""
    payload = {
        "products": [
            {
                "id": "nonsense",
                "name": "Nonsense",
                "per_100g": {"kcal": 1200, "carbs_g": 10, "protein_g": 10, "fat_g": 10},
                "grid": {"kind": "mass", "step_g": 10, "min_g": 10, "max_g": 50},
                "meals": ["dinner"],
            }
        ]
    }
    pantry = load_pantry(_write(tmp_path, payload))
    assert len(pantry) == 1
    assert "nonsense" in check_pantry(pantry)


# --------------------------------------------------------------------------
# Barcodes
# --------------------------------------------------------------------------


def test_barcode_is_normalised_on_load(tmp_path):
    entry = {
        "id": "x",
        "name": "X",
        "barcode": " 3017-6204-22003 ",
        "per_100g": {"kcal": 100, "carbs_g": 1, "protein_g": 1, "fat_g": 1},
        "grid": {"kind": "mass", "step_g": 10, "min_g": 10, "max_g": 50},
        "meals": ["dinner"],
    }
    pantry = load_pantry(_write(tmp_path, {"products": [entry]}))
    assert pantry[0].barcode == "3017620422003"


def test_a_mistyped_barcode_is_reported_by_the_check(tmp_path):
    """A wrong barcode does not fail loudly -- it points at a different food."""
    entry = {
        "id": "x",
        "name": "X",
        "barcode": "3017620422004",
        "per_100g": {"kcal": 100, "carbs_g": 1, "protein_g": 1, "fat_g": 1},
        "grid": {"kind": "mass", "step_g": 10, "min_g": 10, "max_g": 50},
        "meals": ["dinner"],
    }
    pantry = load_pantry(_write(tmp_path, {"products": [entry]}))
    problems = check_pantry(pantry)
    assert "x" in problems
    assert any("barcode" in issue and "check digit" in issue for issue in problems["x"])


def test_products_without_a_barcode_are_fine(pantry_file):
    """The seed pantry carries none, and must still pass."""
    pantry = load_pantry(pantry_file)
    assert all(p.barcode is None for p in pantry)
    assert check_pantry(pantry) == {}
