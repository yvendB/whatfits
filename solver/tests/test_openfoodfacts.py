"""Mapping Open Food Facts records onto our model.

No network. The fixtures below are trimmed copies of real API responses, and
the awkward ones are real too: partial nutrition and absent pack sizes are the
normal case for supermarket own brands, not an edge case.
"""

from __future__ import annotations

import pytest

from whatfits.openfoodfacts import Match, _to_match, parse_quantity


# --------------------------------------------------------------------------
# Pack sizes
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("320g", 320.0),
        ("500 g", 500.0),
        ("1 kg", 1000.0),
        ("1,5 kg", 1500.0),
        ("2 x 150 g", 300.0),
        ("6 × 25 g", 150.0),
        ("425 g (240 g)", 425.0),
    ],
)
def test_pack_sizes_are_parsed(raw, expected):
    assert parse_quantity(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["500 ml", "1 l", "", None, "family size", "12 pieces"])
def test_unparseable_quantities_return_none(raw):
    """Volumes included: millilitres are only grams for water, and guessing a
    density would silently corrupt the nutrition maths."""
    assert parse_quantity(raw) is None


# --------------------------------------------------------------------------
# Record mapping
# --------------------------------------------------------------------------


COMPLETE = {
    "code": "4250193181802",
    "product_name": "Rinderhack",
    "brands": "Packlhof",
    "quantity": "320g",
    "nutriments": {
        "energy-kcal_100g": 263,
        "carbohydrates_100g": 0.5,
        "proteins_100g": 19,
        "fat_100g": 21,
    },
}


def test_a_complete_record_maps_cleanly():
    match = _to_match(COMPLETE)
    assert match.complete
    assert match.missing == ()
    assert match.barcode == "4250193181802"
    assert match.pack_g == pytest.approx(320.0)
    assert match.nutrition.kcal == pytest.approx(263)
    assert match.nutrition.protein_g == pytest.approx(19)


def test_a_missing_macro_makes_the_record_unusable():
    """Partial nutrition must not become a product with silent zeros in it."""
    entry = {**COMPLETE, "nutriments": {k: v for k, v in COMPLETE["nutriments"].items()
                                        if k != "carbohydrates_100g"}}
    match = _to_match(entry)
    assert match.nutrition is None
    assert "carbohydrates" in match.missing
    assert not match.complete


def test_a_missing_pack_size_is_reported_but_keeps_the_nutrition():
    entry = {**COMPLETE}
    entry.pop("quantity")
    match = _to_match(entry)
    assert match.pack_g is None
    assert match.missing == ("pack size",)
    assert match.nutrition is not None


def test_an_empty_record_reports_everything_missing():
    match = _to_match({"code": "1", "nutriments": {}})
    assert set(match.missing) == {"energy", "carbohydrates", "protein", "fat", "pack size"}
    assert match.nutrition is None


def test_brands_arrive_as_a_list_from_one_endpoint_and_a_string_from_the_other():
    as_list = _to_match({**COMPLETE, "brands": ["Packlhof", "Edeka"]})
    as_string = _to_match({**COMPLETE, "brands": "Packlhof, Edeka"})
    assert as_list.brands == as_string.brands == "Packlhof, Edeka"


def test_non_numeric_nutriment_is_treated_as_missing():
    entry = {**COMPLETE, "nutriments": {**COMPLETE["nutriments"], "fat_100g": "traces"}}
    match = _to_match(entry)
    assert "fat" in match.missing
    assert match.nutrition is None


# --------------------------------------------------------------------------
# Presentation
# --------------------------------------------------------------------------


def test_label_adds_the_brand_when_the_name_does_not_carry_it():
    assert _to_match(COMPLETE).label == "Rinderhack (Packlhof)"


def test_label_does_not_repeat_a_brand_already_in_the_name():
    entry = {**COMPLETE, "product_name": "Grobe Bratwurst - Purland", "brands": "Purland"}
    assert _to_match(entry).label == "Grobe Bratwurst - Purland"


def test_unnamed_products_still_get_a_label():
    assert _to_match({"code": "1", "nutriments": {}}).label == "(unnamed product)"


def test_match_is_immutable():
    with pytest.raises(Exception):
        _to_match(COMPLETE).barcode = "nope"  # type: ignore[misc]
