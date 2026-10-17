# Design notes

Background on the choices in [the README](../README.md).

- **Tests never touch a selector.** Journeys call `StoreFlow` and its page
  objects (`flow.inventory`, `flow.cart`, ...); locators live only in page classes.
- **Resilient locators.** Each element is an ordered tuple, stable `data-test`
  hook first and a class/id fallback second. `BasePage.locator_any` resolves to
  whichever the current build renders (a test proves the fallback works).
- **Verified actions.** `InventoryPage.add` returns `True` only when the card's
  button flips to "Remove"; it never reports optimistic success.
- **Independent oracles.** The order-total check takes its expected prices from
  the catalogue, not from the overview it checks; sorting is checked against the
  rendered list; persona expectations are data, so the healthy and the faulty
  accounts run through the same test.
- **Money is `Decimal`.** Price parsing is currency-symbol agnostic and reads a
  single contiguous number. The tax rate comes from config as an exact
  `Decimal`. The live store prints its item total as an unrounded float sum
  (`59.980000000000004` for a bike light and a fleece jacket); the check rounds
  that to the cent and attaches the raw value.
- **Data-driven, typed.** Rows from any format are coerced and validated once
  (`OrderCase.from_dict` and friends), so CSV strings and JSON lists behave the
  same; a unit test enforces that the three order files agree.
