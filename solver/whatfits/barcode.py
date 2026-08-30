"""Barcode handling.

A barcode is the join key between what is physically in the cupboard and what
a product database knows about it. Open Food Facts is indexed by exactly this
number, so getting it right in our own data is what makes a lookup possible at
all -- and a mistyped one silently points at the wrong food.

Every retail barcode is a GTIN: GTIN-8, -12 (UPC-A), -13 (EAN-13) or -14. All
of them carry a mod-10 check digit, so a typo is detectable without a network
call. That is worth doing at entry, in the same spirit as the nutrition
plausibility check.
"""

from __future__ import annotations

VALID_LENGTHS = (8, 12, 13, 14)


def normalise(raw: str) -> str:
    """Strip separators and surrounding whitespace. Does not validate."""
    return "".join(ch for ch in str(raw).strip() if not ch.isspace() and ch != "-")


def check_digit(digits: str) -> int:
    """The mod-10 check digit for a GTIN body (the code without its last digit).

    Weights alternate 3 and 1 from the right, which is why the parity depends
    on the length of the body rather than being fixed.
    """
    total = 0
    for index, char in enumerate(reversed(digits)):
        weight = 3 if index % 2 == 0 else 1
        total += int(char) * weight
    return (10 - total % 10) % 10


def problems(raw: str) -> list[str]:
    """Everything wrong with this barcode. Empty means it is a well-formed GTIN."""
    code = normalise(raw)
    found: list[str] = []

    if not code:
        return ["barcode is empty"]

    if not code.isdigit():
        found.append("barcode contains characters that are not digits")
        return found

    if len(code) not in VALID_LENGTHS:
        found.append(
            f"barcode is {len(code)} digits; a GTIN has "
            + ", ".join(str(n) for n in VALID_LENGTHS[:-1])
            + f" or {VALID_LENGTHS[-1]}"
        )
        return found

    expected = check_digit(code[:-1])
    if int(code[-1]) != expected:
        found.append(
            f"check digit is {code[-1]}, but the other digits imply {expected}"
            " -- most likely a typo"
        )

    return found


def is_valid(raw: str) -> bool:
    return not problems(raw)
