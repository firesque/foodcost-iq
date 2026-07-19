"""Vendor & price-trend analytics."""
from __future__ import annotations

import numpy as np
import pandas as pd


def price_history(purchases: pd.DataFrame) -> pd.DataFrame:
    """Per (vendor, item) daily unit-price history.

    Split-case purchases are excluded: their per-each price is not
    comparable to full-case prices and produces phantom "price spikes".
    """
    df = purchases[purchases["unit_price"] > 0].copy()
    if "uom" in df.columns:
        df = df[df["uom"] != "SPLIT"]
    return (df.groupby(["vendor", "item_no", "description", "date"], as_index=False)
              .agg(unit_price=("unit_price", "median"),
                   qty=("qty", "sum"),
                   spend=("extended_price", "sum")))


def price_changes(purchases: pd.DataFrame, min_purchases: int = 2) -> pd.DataFrame:
    """First-vs-last unit price change per vendor item across the window."""
    hist = price_history(purchases)
    rows = []
    for (vendor, item_no, desc), g in hist.groupby(["vendor", "item_no", "description"]):
        g = g.sort_values("date")
        if len(g) < min_purchases:
            continue
        first, last = g.iloc[0], g.iloc[-1]
        if first["unit_price"] <= 0:
            continue
        chg = (last["unit_price"] - first["unit_price"]) / first["unit_price"] * 100
        # a >3x move within one period is a pack-size or data anomaly,
        # not a market price change — surfaced by data quality, not here
        if abs(chg) > 200:
            continue
        rows.append({
            "vendor": vendor, "item_no": item_no, "description": desc,
            "first_date": first["date"], "last_date": last["date"],
            "first_price": first["unit_price"], "last_price": last["unit_price"],
            "pct_change": chg,
            "total_spend": g["spend"].sum(),
            "n_purchases": len(g),
            "dollar_impact": (last["unit_price"] - first["unit_price"]) * g["qty"].sum(),
        })
    df = pd.DataFrame(rows)
    return df.sort_values("pct_change", ascending=False) if not df.empty else df


def vendor_summary(purchases: pd.DataFrame) -> pd.DataFrame:
    """Spend / invoices / items by vendor."""
    return (purchases.groupby("vendor", as_index=False)
            .agg(spend=("extended_price", "sum"),
                 invoices=("invoice_no", "nunique"),
                 line_items=("item_no", "size"),
                 unique_items=("item_no", "nunique"),
                 first_date=("date", "min"),
                 last_date=("date", "max")))


def cross_vendor_comparison(purchases: pd.DataFrame,
                            invoice_map: pd.DataFrame) -> pd.DataFrame:
    """Ingredients purchased from more than one vendor, with price posture."""
    px = purchases.merge(
        invoice_map[["vendor", "item_no", "ingredient_clean"]],
        on=["vendor", "item_no"], how="inner")
    px = px[px["ingredient_clean"].notna()]
    agg = (px.groupby(["ingredient_clean", "vendor"], as_index=False)
             .agg(spend=("extended_price", "sum"),
                  avg_case_price=("unit_price", "mean"),
                  cases=("qty", "sum")))
    multi = agg.groupby("ingredient_clean")["vendor"].transform("nunique") > 1
    return agg[multi].sort_values(["ingredient_clean", "vendor"])


def spend_by_category(purchases: pd.DataFrame,
                      invoice_map: pd.DataFrame) -> pd.DataFrame:
    """Vendor spend split by mapped ingredient category (fallback: invoice category)."""
    px = purchases.merge(
        invoice_map[["vendor", "item_no", "ingredient_category"]],
        on=["vendor", "item_no"], how="left")
    px["category"] = px["ingredient_category"].fillna(px["category"])
    return (px.groupby(["vendor", "category"], as_index=False)
              .agg(spend=("extended_price", "sum")))


def weekly_spend(purchases: pd.DataFrame) -> pd.DataFrame:
    """Weekly spend by vendor for trend charts."""
    df = purchases.dropna(subset=["date"]).copy()
    if df.empty:
        return df
    df["week"] = df["date"].dt.to_period("W").dt.start_time
    return (df.groupby(["week", "vendor"], as_index=False)
              .agg(spend=("extended_price", "sum")))
