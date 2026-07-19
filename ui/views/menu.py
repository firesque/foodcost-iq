"""Menu item profitability page."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from foodcost.ai_engine.insights import _pretty
from foodcost.config import FOOD_COST_TARGET_PCT, HIGH_FOOD_COST_PCT
from ui import theme
from ui.theme import fmt_money


def render(b) -> None:
    theme.hero("Menu Profitability",
               "Every menu item ranked by contribution — spot the stars, "
               "the workhorses and the margin leaks.", "MENU ENGINEERING")

    p = b.profit[b.profit["recipe"].notna()].copy()
    p["Item"] = p["recipe"].map(_pretty)
    p = p[p["qty_sold"] > 0]

    loc = st.multiselect("Locations", sorted(b.pos["location"].unique()),
                         placeholder="All locations")
    if loc:
        pos = b.pos[b.pos["location"].isin(loc)]
        df = pos.merge(b.pos_map[["item", "recipe"]], on="item", how="left")
        agg = (df.groupby("recipe", dropna=True, as_index=False)
                 .agg(qty_sold=("qty_sold", "sum"), revenue=("revenue", "sum")))
        agg = agg.merge(b.menu_costs, on="recipe", how="left")
        agg["recipe_cost"] = agg["recipe_cost"].fillna(0.0)
        agg["food_cost"] = agg["recipe_cost"] * agg["qty_sold"]
        agg["gross_profit"] = agg["revenue"] - agg["food_cost"]
        agg["food_cost_pct"] = (agg["food_cost"] / agg["revenue"] * 100).where(
            agg["revenue"] > 0)
        agg["avg_price"] = (agg["revenue"] / agg["qty_sold"])
        p = agg
        p["Item"] = p["recipe"].map(_pretty)
        p = p[p["qty_sold"] > 0]

    real = p[p["revenue"] > 0].copy()
    theme.metric_row([
        ("Menu Items Sold", f"{len(p):,}", "", "neutral"),
        ("Revenue (mapped items)", fmt_money(real['revenue'].sum())),
        ("Avg Food Cost %",
         f"{(real['food_cost'].sum() / real['revenue'].sum() * 100):,.1f}%"
         if real['revenue'].sum() else "—"),
        ("Gross Profit", fmt_money(real['gross_profit'].sum())),
    ])

    # ---------------- menu engineering quadrant ----------------
    theme.section("Menu Engineering Matrix",
                  "volume vs margin — bubble size = revenue")
    q = real[real["food_cost_pct"].notna() & (real["revenue"] > 100)].copy()
    if not q.empty:
        med_vol = q["qty_sold"].median()
        q["margin_pct"] = 100 - q["food_cost_pct"]
        med_margin = q["margin_pct"].median()

        def quadrant(r):
            hi_vol = r["qty_sold"] >= med_vol
            hi_m = r["margin_pct"] >= med_margin
            if hi_vol and hi_m:
                return "Star"
            if hi_vol:
                return "Workhorse (reprice)"
            if hi_m:
                return "Puzzle (promote)"
            return "Dog (rework)"

        q["class"] = q.apply(quadrant, axis=1)
        fig = px.scatter(
            q, x="qty_sold", y="margin_pct", size="revenue", color="class",
            hover_name="Item",
            color_discrete_map={
                "Star": theme.ACCENT, "Workhorse (reprice)": theme.GOLD,
                "Puzzle (promote)": theme.BLUE, "Dog (rework)": theme.RED},
            labels={"qty_sold": "Units sold", "margin_pct": "Gross margin %"},
            size_max=42, log_x=True)
        fig.add_hline(y=med_margin, line_dash="dot", line_color="#B6C0CE")
        fig.add_vline(x=med_vol, line_dash="dot", line_color="#B6C0CE")
        fig.update_layout(height=430)
        st.plotly_chart(fig, use_container_width=True)

    # ---------------- ranked table ----------------
    theme.section("Item-Level P&L")
    c1, c2, c3 = st.columns([1.2, 1, 1])
    search = c1.text_input("Search items", placeholder="e.g. omelet")
    only_flagged = c2.toggle("Only flagged items", value=False)
    sort_by = c3.selectbox("Sort by", ["Gross profit", "Revenue", "Food cost %",
                                       "Units sold"])

    t = real.copy()
    t["margin_rank"] = t["gross_profit"].rank(ascending=False).astype(int)
    t["flag"] = np.select(
        [t["food_cost_pct"] >= HIGH_FOOD_COST_PCT,
         t["food_cost_pct"] >= FOOD_COST_TARGET_PCT,
         t["food_cost_pct"].isna()],
        ["Reprice / re-portion", "Watch", "No recipe cost"],
        default="Healthy")
    if search:
        t = t[t["Item"].str.contains(search, case=False, na=False)]
    if only_flagged:
        t = t[t["flag"].isin(["Reprice / re-portion", "Watch"])]
    key = {"Gross profit": "gross_profit", "Revenue": "revenue",
           "Food cost %": "food_cost_pct", "Units sold": "qty_sold"}[sort_by]
    t = t.sort_values(key, ascending=(sort_by == "Food cost %") is False or False,
                      na_position="last")
    t = t.sort_values(key, ascending=False, na_position="last")

    show = t[["margin_rank", "Item", "qty_sold", "avg_price", "recipe_cost",
              "revenue", "gross_profit", "food_cost_pct", "flag"]].rename(columns={
        "margin_rank": "#", "qty_sold": "Sold", "avg_price": "Avg Price",
        "recipe_cost": "Plate Cost", "revenue": "Revenue",
        "gross_profit": "Gross Profit", "food_cost_pct": "Food Cost %",
        "flag": "Flag"})
    st.dataframe(
        show.style.format({
            "Sold": "{:,.0f}", "Avg Price": "${:,.2f}", "Plate Cost": "${:,.2f}",
            "Revenue": "${:,.0f}", "Gross Profit": "${:,.0f}",
            "Food Cost %": "{:,.1f}%"})
        .background_gradient(subset=["Food Cost %"], cmap="RdYlGn_r",
                             vmin=15, vmax=55)
        .map(lambda v: "color:#C0392B;font-weight:600"
             if v == "Reprice / re-portion" else "", subset=["Flag"]),
        use_container_width=True, hide_index=True, height=520)

    # ---------------- item drilldown ----------------
    theme.section("Recipe Drilldown", "plate cost build-up by ingredient")
    pick = st.selectbox("Choose an item",
                        sorted(real["Item"].unique()), index=None,
                        placeholder="Select a menu item…")
    if pick:
        recipe = real.loc[real["Item"] == pick, "recipe"].iloc[0]
        detail = b.exploded[b.exploded["recipe"] == recipe].copy()
        if detail.empty:
            st.info("No exploded ingredient detail for this item.")
        else:
            detail = detail.sort_values("book_cost", ascending=True)
            fig = px.bar(detail, x="book_cost", y="ingredient_clean",
                         orientation="h",
                         labels={"book_cost": "cost per plate ($)",
                                 "ingredient_clean": ""},
                         color_discrete_sequence=[theme.ACCENT])
            fig.update_layout(height=max(220, 40 * len(detail)),
                              xaxis_tickprefix="$", xaxis_tickformat=",.2f")
            st.plotly_chart(fig, use_container_width=True)
            row = real[real["recipe"] == recipe].iloc[0]
            theme.metric_row([
                ("Plate cost", f"${row['recipe_cost']:,.2f}"),
                ("Avg selling price", f"${row['avg_price']:,.2f}"),
                ("Food cost %", f"{row['food_cost_pct']:,.1f}%"
                 if pd.notna(row['food_cost_pct']) else "—"),
                ("Period gross profit", fmt_money(row["gross_profit"])),
            ])
