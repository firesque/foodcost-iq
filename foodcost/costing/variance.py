"""Waste & variance intelligence.

The primary comparison is done in DOLLARS (purchased spend vs theoretical
usage cost) because vendor pack sizes are frequently ambiguous while
dollar amounts are exact. Where clean physical conversions exist they are
shown as supplementary detail.

Waste-risk score (0-100) blends:
* variance ratio  (purchased / theoretical)      — 45%
* dollar magnitude of the excess                 — 30%
* category perishability                         — 25%
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from foodcost.config import CATEGORY_PERISHABILITY


def ingredient_variance(purchases: pd.DataFrame, invoice_map: pd.DataFrame,
                        theo: pd.DataFrame,
                        period: tuple | None = None) -> pd.DataFrame:
    """Compare purchased spend vs theoretical usage cost per ingredient.

    purchases : invoice line items [vendor, item_no, date, extended_price, ...]
    invoice_map : [vendor, item_no, ingredient, ...]
    theo : theoretical usage [ingredient, theo_qty, theo_cost, base_unit, category]
    period : optional (start, end) to filter purchases to the POS window
    """
    px = purchases.copy()
    if period and "date" in px.columns:
        start, end = period
        px = px[(px["date"] >= start) & (px["date"] <= end)]

    px = px.merge(
        invoice_map[["vendor", "item_no", "ingredient", "ingredient_clean",
                     "ingredient_category"]],
        on=["vendor", "item_no"], how="left")

    bought = (px[px["ingredient"].notna()]
              .groupby(["ingredient", "ingredient_clean", "ingredient_category"],
                       as_index=False)
              .agg(purchased_dollars=("extended_price", "sum"),
                   cases=("qty", "sum"),
                   vendors=("vendor", lambda s: ", ".join(sorted(set(s))))))
    bought = bought.rename(columns={"ingredient_category": "category"})

    t = theo.groupby(["ingredient", "ingredient_clean", "category", "base_unit"],
                     as_index=False).agg(theo_qty=("theo_qty", "sum"),
                                         theo_cost=("theo_cost", "sum"))

    df = bought.merge(
        t[["ingredient", "base_unit", "theo_qty", "theo_cost"]],
        on="ingredient", how="outer")
    for col in ("purchased_dollars", "theo_cost", "theo_qty", "cases"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["category"] = df["category"].fillna("MISC")

    df["variance_dollars"] = df["purchased_dollars"] - df["theo_cost"]
    df["variance_ratio"] = np.where(
        df["theo_cost"] > 0, df["purchased_dollars"] / df["theo_cost"], np.nan)

    df["waste_risk"] = _risk_score(df)
    df["est_waste_dollars"] = np.where(
        (df["variance_dollars"] > 0) & (df["theo_cost"] > 0),
        df["variance_dollars"], 0.0)
    df["flag"] = df.apply(_flag, axis=1)
    return df.sort_values("waste_risk", ascending=False).reset_index(drop=True)


def _risk_score(df: pd.DataFrame) -> pd.Series:
    ratio = df["variance_ratio"].copy()
    # ratio component: 1.0 -> 0, 2.0+ -> 1
    ratio_score = ((ratio - 1.0).clip(lower=0) / 1.0).clip(upper=1.0).fillna(0)
    # if we bought it but never theoretically used it, that's max ratio risk
    ratio_score = ratio_score.where(df["theo_cost"] > 0, 0.9)
    ratio_score = ratio_score.where(df["purchased_dollars"] > 0, 0.0)

    excess = (df["purchased_dollars"] - df["theo_cost"]).clip(lower=0)
    max_excess = max(excess.max(), 1.0)
    dollar_score = (excess / max_excess) ** 0.5      # dampen outlier dominance

    perish = df["category"].map(CATEGORY_PERISHABILITY).fillna(0.4)

    score = 100 * (0.45 * ratio_score + 0.30 * dollar_score + 0.25 * perish)
    # nothing purchased -> no waste exposure
    return score.where(df["purchased_dollars"] > 0, 0.0).round(1)


def _flag(r: pd.Series) -> str:
    if r["purchased_dollars"] > 0 and r["theo_cost"] == 0:
        return "No theoretical usage (unmapped or unsold)"
    if pd.notna(r["variance_ratio"]) and r["variance_ratio"] >= 1.5:
        return "Purchasing far exceeds usage"
    if pd.notna(r["variance_ratio"]) and r["variance_ratio"] >= 1.25:
        return "Over-purchasing"
    if pd.notna(r["variance_ratio"]) and r["variance_ratio"] <= 0.7:
        return "Purchases below usage (stock draw-down or under-portioning)"
    return "In line"


def category_variance(var: pd.DataFrame) -> pd.DataFrame:
    """Roll ingredient variance up to category level."""
    agg = (var.groupby("category", as_index=False)
           .agg(purchased_dollars=("purchased_dollars", "sum"),
                theo_cost=("theo_cost", "sum"),
                est_waste_dollars=("est_waste_dollars", "sum"),
                avg_risk=("waste_risk", "mean")))
    agg["variance_ratio"] = np.where(
        agg["theo_cost"] > 0, agg["purchased_dollars"] / agg["theo_cost"], np.nan)
    return agg.sort_values("est_waste_dollars", ascending=False)
