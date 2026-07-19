"""Scenario studio: what-if modeling."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from foodcost.ai_engine.insights import _pretty
from foodcost.costing.scenarios import Scenario, run_scenario
from ui import theme
from ui.theme import fmt_money


def render(b) -> None:
    theme.hero("Scenario Studio",
               "Model price shocks, menu repricing, portion changes and "
               "volume shifts — see the P&L impact before you commit.",
               "WHAT-IF")

    profit = b.profit[(b.profit["recipe"].notna())
                      & (b.profit["revenue"] > 0)].copy()
    if profit.empty:
        st.info("Need POS + recipe data to model scenarios.")
        return

    names = {r: _pretty(r) for r in profit["recipe"]}
    ing_options = sorted(b.exploded["ingredient_clean"].dropna().unique())

    with st.container(border=True):
        st.markdown("#### Build your scenario")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Ingredient cost shock**")
            ings = st.multiselect("Ingredients affected", ing_options,
                                  placeholder="e.g. Eggs, Bacon…")
            ing_pct = st.slider("Ingredient price change %", -30, 60, 0, 1)
            st.markdown("**Sales volume**")
            vol_pct = st.slider("Volume change %", -30, 30, 0, 1)
        with c2:
            st.markdown("**Menu actions** (apply to selected items, or all)")
            items = st.multiselect(
                "Menu items", sorted(profit["recipe"], key=lambda r: names[r]),
                format_func=lambda r: names[r], placeholder="All items")
            price_pct = st.slider("Menu price change %", -10, 25, 0, 1)
            portion_pct = st.slider("Portion size change %", -25, 25, 0, 1)

    sc = Scenario(ingredient_price_pct=ing_pct, ingredients=ings,
                  menu_price_pct=price_pct, portion_pct=portion_pct,
                  volume_pct=vol_pct, menu_items=items)
    res = run_scenario(profit, b.exploded, sc)
    before, after = res["before"], res["after"]

    delta = res["profit_delta"]
    theme.section("Impact")
    theme.metric_row([
        ("Gross Profit Δ", fmt_money(delta),
         "per period", "good" if delta >= 0 else "bad"),
        ("Food Cost % (before → after)",
         f"{before['food_cost_pct']:,.1f}% → {after['food_cost_pct']:,.1f}%",
         f"{after['food_cost_pct'] - before['food_cost_pct']:+.2f} pts",
         "good" if after['food_cost_pct'] <= before['food_cost_pct'] else "bad"),
        ("Revenue", f"{fmt_money(before['revenue'])} → {fmt_money(after['revenue'])}"),
        ("Food Cost $", f"{fmt_money(before['food_cost'])} → {fmt_money(after['food_cost'])}"),
    ])

    fig = go.Figure()
    cats = ["Revenue", "Food cost", "Gross profit"]
    fig.add_bar(name="Before", x=cats,
                y=[before["revenue"], before["food_cost"], before["gross_profit"]],
                marker_color="#9AA2AF")
    fig.add_bar(name="After", x=cats,
                y=[after["revenue"], after["food_cost"], after["gross_profit"]],
                marker_color=theme.ACCENT)
    fig.update_layout(barmode="group", height=340, yaxis_tickprefix="$",
                      yaxis_tickformat=",.0f")
    st.plotly_chart(fig, use_container_width=True)

    if any([ing_pct, price_pct, portion_pct, vol_pct]):
        theme.section("Most Affected Menu Items")
        d = res["detail"].copy()
        d["Item"] = d["recipe"].map(names)
        d = d[d["profit_delta"].abs() > 1]
        d = d.reindex(d["profit_delta"].abs().sort_values(ascending=False).index)
        show = d.head(15)[["Item", "qty_sold", "unit_price", "new_unit_price",
                           "recipe_cost", "new_recipe_cost", "profit_delta"]]
        st.dataframe(show.rename(columns={
            "qty_sold": "Sold", "unit_price": "Price", "new_unit_price": "New Price",
            "recipe_cost": "Plate Cost", "new_recipe_cost": "New Plate Cost",
            "profit_delta": "Profit Δ"}).style.format({
                "Sold": "{:,.0f}", "Price": "${:,.2f}", "New Price": "${:,.2f}",
                "Plate Cost": "${:,.2f}", "New Plate Cost": "${:,.2f}",
                "Profit Δ": "${:+,.0f}"})
            .map(lambda v: "", subset=["Item"]),
            use_container_width=True, hide_index=True)
    else:
        st.caption("Adjust any slider above to model a scenario.")
