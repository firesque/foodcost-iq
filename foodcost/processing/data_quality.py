"""Data-quality checks across all sources."""
from __future__ import annotations

import pandas as pd

from foodcost.config import SUSPICIOUS_UNIT_PRICE


def run_checks(recipes: pd.DataFrame, ingredients: pd.DataFrame,
               purchases: pd.DataFrame, invoice_map: pd.DataFrame,
               pos: pd.DataFrame, pos_map: pd.DataFrame) -> pd.DataFrame:
    """Return a tidy issues table [severity, check, detail, count]."""
    issues: list[dict] = []

    def add(severity: str, check: str, detail: str, count: int) -> None:
        if count:
            issues.append({"severity": severity, "check": check,
                           "detail": detail, "count": count})

    # POS items with no recipe match
    unmatched_pos = pos_map[pos_map["recipe"].isna()]
    if not unmatched_pos.empty:
        sold = pos.groupby("item")["qty_sold"].sum()
        vol = unmatched_pos["item"].map(sold).fillna(0)
        big = unmatched_pos.loc[vol > 25, "item"].tolist()
        add("warning", "POS items without a recipe",
            "High-volume examples: " + ", ".join(big[:8]) if big else
            "Low-volume items only", len(unmatched_pos))

    # invoice items with no ingredient match
    unmatched_inv = invoice_map[invoice_map["ingredient"].isna()]
    if not unmatched_inv.empty:
        spend = (purchases.groupby(["vendor", "item_no"])["extended_price"].sum())
        um = unmatched_inv.set_index(["vendor", "item_no"]).index
        um_spend = spend[spend.index.isin(um)].sort_values(ascending=False)
        top = ", ".join(
            unmatched_inv.set_index(["vendor", "item_no"])
            .loc[um_spend.index[:5], "description"].tolist()
        ) if len(um_spend) else ""
        add("warning", "Invoice items not mapped to any recipe ingredient",
            f"${um_spend.sum():,.0f} of spend unmapped. Top: {top}",
            len(unmatched_inv))

    # weak fuzzy matches
    weak = invoice_map[(invoice_map["method"] == "fuzzy")
                       & (invoice_map["confidence"] < 90)]
    add("info", "Low-confidence ingredient matches (review advised)",
        ", ".join(weak["description"].head(6).tolist()), len(weak))

    # recipe ingredients with missing qty or measure
    miss_qty = ingredients[ingredients["qty"].isna()
                           | ingredients["measure"].isna()]
    add("warning", "Recipe lines with missing quantity or unit",
        ", ".join(miss_qty["recipe"].drop_duplicates().head(6)), len(miss_qty))

    # unknown units
    from foodcost.utils.units import parse_measure
    units_ok = ingredients.dropna(subset=["measure"])
    unknown_units = units_ok[[
        parse_measure(1.0, str(m)).dimension == "unknown"
        for m in units_ok["measure"]]]
    add("info", "Unrecognized units of measure",
        ", ".join(sorted(set(map(str, unknown_units["measure"])))[:8]),
        len(unknown_units))

    # suspicious prices
    weird = purchases[(purchases["unit_price"] > SUSPICIOUS_UNIT_PRICE)
                      | (purchases["unit_price"] < 0)]
    add("warning", "Suspicious invoice unit prices",
        ", ".join(weird["description"].head(5)), len(weird))

    # duplicate vendor items (same description, different item numbers)
    dup = (invoice_map.groupby(["vendor", "description"])["item_no"]
           .nunique().reset_index())
    dups = dup[dup["item_no"] > 1]
    add("info", "Duplicate vendor items (same description, multiple item numbers)",
        ", ".join(dups["description"].head(5)), len(dups))

    # POS rows with sales but zero revenue
    zero_rev = pos[(pos["qty_sold"] > 0) & (pos["revenue"] == 0)]
    hi = (zero_rev.groupby("item")["qty_sold"].sum()
          .sort_values(ascending=False).head(6).index.tolist())
    add("info", "POS items sold with $0 revenue (comps/modifiers?)",
        ", ".join(hi), len(zero_rev))

    # menu items in recipes never sold
    sold_recipes = set(pos_map["recipe"].dropna())
    all_menu = set(recipes.loc[recipes["recipe_type"] == "menu_item", "recipe"])
    never = sorted(all_menu - sold_recipes)
    add("info", "Recipes with no POS sales in period",
        ", ".join(never[:6]), len(never))

    return pd.DataFrame(issues)
