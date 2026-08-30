"""Looking products up in Open Food Facts, by barcode or by name.

Open Food Facts is indexed by barcode, which makes it the natural answer to the
cold-start problem in the concept doc: scanning a packet is the least work a
user can possibly do, and it is the same key the database is built around.

Two things this module is careful about, both learned by measuring rather than
assuming:

  * **Coverage is uneven, in a specific place.** German products carry all four
    macros about 95-97 % of the time, whichever way the results are sorted. But
    fresh meat is a hole: a full census of Kaufland's Purland brand puts it at
    53 %, and Lidl's Landjunker at 77 %. A lookup that quietly returns half a
    product is worse than one that says what is missing, so `Match.missing`
    names every gap and nothing is invented to paper over it.

  * **The portion grid can never come from here.** Open Food Facts knows the net
    weight; it does not know the drained weight of a tin, how many pieces are in
    a pack, or whether you are willing to use half of one. That judgement is the
    user's, and it is exactly what makes this app different from a lookup table.

Kept deliberately separate from the solver, which stays offline and has no
dependencies. Nothing in `search.py` or `model.py` imports this.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .model import Nutrition

USER_AGENT = "WhatFits-prototype/0.1 (https://github.com/yvendB/whatfits)"

PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
SEARCH_URL = "https://search.openfoodfacts.org/search"

_FIELDS = "code,product_name,brands,quantity,nutriments"

# Open Food Facts spells protein "proteins" and energy "energy-kcal".
_NUTRIENT_KEYS = {
    "energy": "energy-kcal_100g",
    "carbohydrates": "carbohydrates_100g",
    "protein": "proteins_100g",
    "fat": "fat_100g",
}


class LookupFailed(RuntimeError):
    """The database could not be reached, or answered with something unusable."""


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

# "500g", "1 kg", "2 x 150 g", "425 g". Volumes are deliberately not accepted:
# millilitres are only grams for water, and guessing a density silently
# corrupts the nutrition maths for exactly the products where it matters.
_QUANTITY = re.compile(
    r"(?:(\d+(?:[.,]\d+)?)\s*[x×]\s*)?(\d+(?:[.,]\d+)?)\s*(kg|g)\b", re.IGNORECASE
)

_TO_GRAMS = {"g": 1.0, "kg": 1000.0}


def parse_quantity(raw: str | None) -> float | None:
    """'2 x 150 g' -> 300.0. Returns None for volumes and anything unparseable."""
    if not raw:
        return None
    match = _QUANTITY.search(raw)
    if not match:
        return None

    count_text, amount_text, unit = match.groups()
    count = float(count_text.replace(",", ".")) if count_text else 1.0
    amount = float(amount_text.replace(",", "."))
    return count * amount * _TO_GRAMS[unit.lower()]


@dataclass(frozen=True)
class Match:
    barcode: str
    name: str
    brands: str
    quantity_raw: str | None
    pack_g: float | None
    nutrition: Nutrition | None
    missing: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.missing

    @property
    def label(self) -> str:
        if self.brands and self.brands.lower() not in self.name.lower():
            return f"{self.name} ({self.brands})"
        return self.name or "(unnamed product)"


def _brands_text(raw) -> str:
    if isinstance(raw, list):
        return ", ".join(str(item) for item in raw if item)
    return str(raw or "").strip()


def _to_match(entry: dict) -> Match:
    nutriments = entry.get("nutriments") or {}
    values: dict[str, float] = {}
    missing: list[str] = []

    for label, key in _NUTRIENT_KEYS.items():
        value = nutriments.get(key)
        if value is None:
            missing.append(label)
        else:
            try:
                values[label] = float(value)
            except (TypeError, ValueError):
                missing.append(label)

    quantity_raw = entry.get("quantity") or None
    pack_g = parse_quantity(quantity_raw)
    if pack_g is None:
        missing.append("pack size")

    nutrition = None
    if not {"energy", "carbohydrates", "protein", "fat"} & set(missing):
        nutrition = Nutrition(
            kcal=values["energy"],
            carbs_g=values["carbohydrates"],
            protein_g=values["protein"],
            fat_g=values["fat"],
        )

    return Match(
        barcode=str(entry.get("code") or ""),
        name=str(entry.get("product_name") or "").strip(),
        brands=_brands_text(entry.get("brands")),
        quantity_raw=quantity_raw,
        pack_g=pack_g,
        nutrition=nutrition,
        missing=tuple(missing),
    )


# --------------------------------------------------------------------------
# Network
# --------------------------------------------------------------------------


def _get(url: str, timeout: float) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return {}
        raise LookupFailed(
            f"Open Food Facts answered {error.code} ({error.reason}). "
            "The service is often busy; try again in a moment."
        ) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise LookupFailed(
            f"could not reach Open Food Facts: {error}. "
            "A lookup needs a network connection; the solver itself does not."
        ) from error
    except json.JSONDecodeError as error:
        raise LookupFailed("Open Food Facts returned something that is not JSON") from error


def lookup(barcode: str, timeout: float = 15.0) -> Match | None:
    """Fetch one product by barcode. None if the database does not have it."""
    url = PRODUCT_URL.format(barcode=urllib.parse.quote(barcode)) + f"?fields={_FIELDS}"
    payload = _get(url, timeout)

    product = payload.get("product")
    if not product:
        return None
    return _to_match(product)


def search(query: str, limit: int = 8, timeout: float = 25.0) -> list[Match]:
    """Free-text search, for when there is no barcode to hand.

    Wanted alongside scanning rather than instead of it: a packet that is
    already open, or one whose barcode the database does not carry, still has
    a name.
    """
    params = urllib.parse.urlencode({"q": query, "page_size": max(1, min(limit, 50))})
    payload = _get(f"{SEARCH_URL}?{params}", timeout)

    entries = payload.get("hits")
    if entries is None:
        entries = payload.get("products", [])

    return [_to_match(entry) for entry in entries][:limit]
