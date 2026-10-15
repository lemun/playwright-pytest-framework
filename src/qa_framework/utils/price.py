"""Price parsing.

Price nodes may read any of:

    "$29.99"                -> 29.99
    "Item total: $39.98"    -> 39.98
    "US $1,234.56"          -> 1234.56
    "£19.99"                -> 19.99
    "$10.00 to $20.00"      -> 10.00      (range -> lowest, see `prefer`)
    "Price unavailable"     -> None

We use ``Decimal`` (not float) so money comparisons and sums are exact, and we
extract the **number regardless of currency symbol**: anchoring to ``$`` would
silently break on a store localised to another currency. This is safe because
callers pass the text of a *dedicated price node* (a card price or a totals
label), not whole-page text, so unrelated figures don't contaminate the result.

Assumption: US-style grouping (``,`` thousands, ``.`` decimals).

The number grammar matches a **single contiguous** numeric run (digits, optional
grouping commas, optional decimals) and strips the commas before parsing. Even if
the grouping is irregular (e.g. ``"1,23,456.78"``), the whole run is read as one
amount (``123456.78``) rather than being split into a tiny fragment. Splitting is
the dangerous failure mode for a money check, because ``prefer="min"`` would
then return the fragment and *understate* the price.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

# A single contiguous monetary run: a leading digit, then any mix of digits and
# grouping commas, with an optional decimal part. Commas are stripped before
# parsing, so irregular grouping collapses to one amount instead of fragmenting.
_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def extract_amounts(text: str | None) -> list[Decimal]:
    """Return every monetary amount found in *text*, in order of appearance."""
    if not text:
        return []
    amounts: list[Decimal] = []
    for token in _NUMBER_RE.findall(text):
        try:
            amounts.append(Decimal(token.replace(",", "")))
        except InvalidOperation:
            continue
    return amounts


def parse_price(text: str | None, prefer: str = "min") -> Decimal | None:
    """Parse a single representative price from *text*.

    For a range ("$10 to $20"), ``prefer`` chooses which bound represents the
    listing: ``"min"`` (default) — the cheapest buyable variant — or ``"max"``.
    Returns ``None`` when no number is present (e.g. "Tap item to see price").
    """
    amounts = extract_amounts(text)
    if not amounts:
        return None
    return min(amounts) if prefer == "min" else max(amounts)
