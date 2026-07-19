"""Ingredient intelligence page."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from foodcost.ai_engine.insights import _pretty
from foodcost.costing.vendors import price_history
from foodcost.utils.units import format_qty
from ui import theme
from ui.theme import fmt_money


def render(b) -> None:
    theme.hero("Ingredient Intelligence",
               "Cost, usage and waste posture for every ingredient — "
               "with the vendor items behind it.", "INGREDIENTS")

    var = b.variance.copy()
    var = var[var["ingredient_clean"].notna()]

    theme.metric_row([
        ("Tracked Ingredients", f"{len(var):,}"),
        ("Purchased $ (mapped)", fmt_money(var["purchased_dollars"].sum())),
        ("Theoretical Usage $", fmt_money(var["theo_cost"].sum())),
        ("Est. Waste $", fmt_money(var["est_waste_dollars"].sum()),
         "purchases above theoretical", "bad"),
    ])

    theme.section("Ingredient Ledger")
    c1, c2 = st.columns([1.4, 1])
    search = c1.text_input("Search ingredients", placeholder="e.g. egg, bacon, strawberry")
    cat = c2.multiselect("Category", sorted(var["category"].dropna().unique()),
                         placeholder="All categories")

    t = var.copy()
    if search:
        t = t[t["ingredient_clean"].str.contains(search, case=False, na=False)]
    if cat:
        t = t[t["category"].isin(cat)]

    show = t[["ingredient_clean", "category", "vendors", "purchased_dollars",
              "theo_cost", "variance_dollars", "variance_ratio", "waste_risk",
              "flag"]].rename(columns={
        "ingredient_clean": "Ingredient", "category": "Category",
        "vendors": "Vendors", "purchased_dollars": "Purchased $",
        "theo_cost": "Theoretical $", "variance_dollars": "Variance $",
        "variance_ratio": "Ratio", "waste_risk": "Risk", "flag": "Flag"})
    st.dataframe(
        show.style.format({
            "Purchased $": "${:,.0f}", "Theoretical $": "${:,.0f}",
            "Variance $": "${:,.0f}", "Ratio": "{:,.2f}", "Risk": "{:,.0f}"})
        .background_gradient(subset=["Risk"], cmap="Reds", vmin=0, vmax=100),
        use_container_width=True, hide_index=True, height=430)

    # ------------------------------------------------ drilldown
    theme.section("Ingredient Drilldown")
    pick = st.selectbox(
        "Choose an ingredient",
        sorted(var["ingredient_clean"].unique()), index=None,
        placeholder="Select an ingredient…")
    if not pick:
        return

    row = var[var["ingredient_clean"] == pick].iloc[0]
    theo_qty = row.get("theo_qty", 0.0)
    unit = row.get("base_unit") or "unit"
    theme.metric_row([
        ("Purchased", fmt_money(row["purchased_dollars"]),
         f"{row['cases']:,.0f} cases", "neutral"),
        ("Theoretical usage", fmt_money(row["theo_cost"]),
         format_qty(theo_qty, str(unit)) if theo_qty else "", "neutral"),
        ("Variance", fmt_money(row["variance_dollars"]),
         f"ratio {row['variance_ratio']:,.2f}" if pd.notna(row["variance_ratio"])
         else "no usage", "bad" if row["variance_dollars"] > 0 else "good"),
        ("Waste risk", f"{row['waste_risk']:,.0f} / 100", row["flag"],
         "bad" if row["waste_risk"] > 55 else "neutral"),
    ])

    # price trend for the vendor items mapped to this ingredient
    items = b.invoice_map[b.invoice_map["ingredient_clean"] == pick]
    px_hist = price_history(b.purchases)
    hist = px_hist.merge(items[["vendor", "item_no"]], on=["vendor", "item_no"])
    c1, c2 = st.columns([1.25, 1])
    with c1:
        theme.section("Case Price Trend", "per vendor item")
        if hist.empty:
            st.info("No purchase history for this ingredient.")
        else:
            fig = px.line(hist.sort_values("date"), x="date", y="unit_price",
                          color="description", markers=True,
                          labels={"unit_price": "case price ($)", "date": ""})
            fig.update_layout(height=330, yaxis_tickprefix="$",
                              legend=dict(font=dict(size=10)))
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        theme.section("Menu Items Using It", "theoretical cost share")
        usage = b.exploded[b.exploded["ingredient_clean"] == pick]
        sold = b.profit[["recipe", "qty_sold"]]
        u = usage.merge(sold, on="recipe", how="left").fillna({"qty_sold": 0})
        u["period_cost"] = u["book_cost"] * u["qty_sold"]
        u = u[u["period_cost"] > 0].nlargest(10, "period_cost")
        if u.empty:
            st.info("Not used by any sold menu item.")
        else:
            u["name"] = u["recipe"].map(_pretty)
            fig = px.bar(u.sort_values("period_cost"), x="period_cost", y="name",
                         orientation="h", labels={"period_cost": "period cost ($)",
                                                  "name": ""},
                         color_discrete_sequence=[theme.BLUE])
            fig.update_layout(height=330, xaxis_tickprefix="$")
            st.plotly_chart(fig, use_container_width=True)

    theme.section("Vendor Items Mapped Here", "review and correct in ingredient_map_overrides.csv")
    m = items[["vendor", "item_no", "description", "confidence", "method"]]
    st.dataframe(m.rename(columns={
        "vendor": "Vendor", "item_no": "Item #", "description": "Vendor Description",
        "confidence": "Match %", "method": "Method"}),
        use_container_width=True, hide_index=True)
