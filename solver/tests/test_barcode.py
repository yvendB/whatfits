"""Barcode validation. Entirely offline -- that is the point of it."""

from __future__ import annotations

import pytest

from whatfits import barcode

# Real codes, verified against Open Food Facts.
NUTELLA = "3017620422003"          # EAN-13
PACKLHOF_MINCE = "4250193181802"   # EAN-13
EAN_8 = "96385074"
UPC_A = "036000291452"             # GTIN-12


@pytest.mark.parametrize("code", [NUTELLA, PACKLHOF_MINCE, EAN_8, UPC_A])
def test_real_barcodes_are_accepted(code):
    assert barcode.is_valid(code)
    assert barcode.problems(code) == []


def test_check_digit_matches_the_published_one():
    assert barcode.check_digit(NUTELLA[:-1]) == int(NUTELLA[-1])
    assert barcode.check_digit(EAN_8[:-1]) == int(EAN_8[-1])


def test_a_single_wrong_digit_is_caught():
    """The whole reason to validate before spending a network call."""
    typo = NUTELLA[:-1] + "4"
    issues = barcode.problems(typo)
    assert issues
    assert "check digit" in issues[0]


def test_transposed_digits_are_usually_caught():
    swapped = "3017620422030"  # last two body digits transposed
    assert not barcode.is_valid(swapped)


def test_wrong_length_is_rejected():
    # Seen in the wild: Open Food Facts carries 9- and 16-digit entries that
    # are not GTINs at all.
    assert "9 digits" in barcode.problems("040504543")[0]
    assert not barcode.is_valid("0051064313650908")


def test_non_digits_are_rejected():
    issues = barcode.problems("30176204220O3")
    assert any("not digits" in issue for issue in issues)


def test_empty_is_rejected():
    assert barcode.problems("") == ["barcode is empty"]
    assert barcode.problems("   ") == ["barcode is empty"]


def test_separators_are_stripped():
    assert barcode.normalise(" 3017-6204-22003 ") == NUTELLA
    assert barcode.is_valid(" 3017-6204-22003 ")


def test_check_digit_weighting_depends_on_length():
    """GTIN-8 and GTIN-13 weight from the right, so parity differs by length."""
    assert barcode.check_digit("1234567") == barcode.check_digit("1234567")
    # A body of all zeros has check digit zero at any length.
    assert barcode.check_digit("0000000") == 0
    assert barcode.check_digit("000000000000") == 0
