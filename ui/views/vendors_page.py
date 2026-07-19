"""Vendor & invoice analysis page."""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from foodcost.costing.vendors import (
    cross_vendor_comparison, spend_by_category, vendor_summary, weekly_spend)
from ui import theme
from ui.theme import fmt_money


def render(b) -> None:
    theme.hero("Vendor & Invoice Analysis",
               "Sysco vs FreshPoint spend, price moves, and invoice-level "
               "drilldown.", "PROCUREMENT")

    px_all = b.purchases
    if px_all.empty:
        st.info("No invoice data loaded.")
        return

    vs = vendor_summary(px_all)
    cards = []
    for _, r in vs.iterrows():
        cards.append((f"{r['vendor']} Spend", fmt_money(r["spend"]),
                      f"{r['invoices']} invoices · {r['unique_items']} SKUs",
                      "neutral"))
    cards.append(("Total Purchases", fmt_money(vs["spend"].sum()),
                  f"{vs['invoices'].sum()} invoices", "neutral"))
    theme.metric_row(cards)

    c1, c2 = st.columns([1.15, 1])
    with c1:
        theme.section("Weekly Spend by Vendor")
        wk = weekly_spend(px_all)
        fig = px.bar(wk, x="week", y="spend", color="vendor",
                     color_discrete_map=theme.VENDOR_COLORS,
                     labels={"week": "", "spend": "spend ($)"})
        fig.update_layout(height=330, yaxis_tickprefix="$", barmode="stack")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        theme.section("Spend by Category & Vendor")
        cat = spend_by_category(px_all, b.invoice_map)
        fig = px.bar(cat, x="spend", y="category", color="vendor",
                     orientation="h", color_discrete_map=theme.VENDOR_COLORS,
                     labels={"spend": "spend ($)", "category": ""})
        fig.update_layout(height=330, xaxis_tickprefix="$")
        st.plotly_chart(fig, use_container_width=True)

    # ---------------- price changes ----------------
    theme.section("Price Moves This Period", "items purchased 2+ times")
    pc = b.price_changes
    if pc.empty:
        st.info("Not enough repeat purchases to compute price changes.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Largest increases**")
            up = pc.head(8)[["vendor", "description", "first_price",
                             "last_price", "pct_change", "dollar_impact"]]
            _pc_table(up, "Reds")
        with c2:
            st.markdown("**Largest decreases**")
            down = pc.tail(8).iloc[::-1][["vendor", "description", "first_price",
                                          "last_price", "pct_change",
                                          "dollar_impact"]]
            _pc_table(down, "Greens_r")

    # ---------------- cross-vendor ----------------
    theme.section("Cross-Vendor Ingredients",
                  "same ingredient purchased from both vendors")
    cross = cross_vendor_comparison(px_all, b.invoice_map)
    if cross.empty:
        st.info("No overlapping ingredients between vendors in this period.")
    else:
        show = cross.rename(columns={
            "ingredient_clean": "Ingredient", "vendor": "Vendor",
            "spend": "Spend $", "avg_case_price": "Avg Case $", "cases": "Cases"})
        st.dataframe(show.style.format({
            "Spend $": "${:,.0f}", "Avg Case $": "${:,.2f}", "Cases": "{:,.0f}"}),
            use_container_width=True, hide_index=True, height=320)

    # ---------------- invoice drilldown ----------------
    theme.section("Invoice Drilldown")
    c1, c2, c3 = st.columns(3)
    vendor = c1.selectbox("Vendor", sorted(px_all["vendor"].unique()))
    sub = px_all[px_all["vendor"] == vendor]
    locs = c2.selectbox("Location", ["All"] + sorted(sub["location"].dropna().unique()))
    if locs != "All":
        sub = sub[sub["location"] == locs]
    inv_ids = (sub.groupby("invoice_no")
               .agg(date=("date", "first"), total=("extended_price", "sum"))
               .sort_values("date", ascending=False))
    label = {i: f"{i} — {r['date']:%b %d} — ${r['total']:,.0f}"
             for i, r in inv_ids.iterrows()}
    pick = c3.selectbox("Invoice", list(label.keys()),
                        format_func=lambda i: label[i])
    if pick:
        lines = sub[sub["invoice_no"] == pick][
            ["item_no", "description", "category", "qty", "uom", "pack_size",
             "unit_price", "extended_price"]]
        st.dataframe(lines.rename(columns={
            "item_no": "Item #", "description": "Description",
            "category": "Category", "qty": "Qty", "uom": "UoM",
            "pack_size": "Pack", "unit_price": "Unit $",
            "extended_price": "Extended $"}).style.format({
                "Qty": "{:,.0f}", "Unit $": "${:,.2f}", "Extended $": "${:,.2f}"}),
            use_container_width=True, hide_index=True, height=420)


def _pc_table(df, cmap: str) -> None:
    show = df.rename(columns={
        "vendor": "Vendor", "description": "Item", "first_price": "First $",
        "last_price": "Last $", "pct_change": "Δ %",
        "dollar_impact": "$ Impact"})
    st.dataframe(
        show.style.format({"First $": "${:,.2f}", "Last $": "${:,.2f}",
                           "Δ %": "{:+,.1f}%", "$ Impact": "${:,.0f}"})
        .background_gradient(subset=["Δ %"], cmap=cmap),
        use_container_width=True, hide_index=True, height=320)
