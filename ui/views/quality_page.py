"""Data quality & mapping review page."""
from __future__ import annotations

import streamlit as st

from ui import theme


def render(b) -> None:
    theme.hero("Data Quality",
               "Trust the numbers: unmatched items, weak mappings and "
               "anomalies that deserve a human eye.", "DATA HEALTH")

    q = b.quality
    n_warn = (q["severity"] == "warning").sum() if not q.empty else 0
    inv_mapped = b.invoice_map["ingredient"].notna().mean() * 100 \
        if not b.invoice_map.empty else 0
    pos_mapped = b.pos_map["recipe"].notna().mean() * 100 \
        if not b.pos_map.empty else 0

    # dollar-weighted invoice coverage
    px = b.purchases.merge(
        b.invoice_map[["vendor", "item_no", "ingredient"]],
        on=["vendor", "item_no"], how="left")
    spend_cov = (px.loc[px["ingredient"].notna(), "extended_price"].sum()
                 / max(px["extended_price"].sum(), 1)) * 100

    theme.metric_row([
        ("Warnings", f"{n_warn}", "", "bad" if n_warn else "good"),
        ("Invoice SKUs Mapped", f"{inv_mapped:,.0f}%",
         f"{spend_cov:,.0f}% of spend", "good" if spend_cov > 80 else "bad"),
        ("POS Items Mapped", f"{pos_mapped:,.0f}%",
         "of distinct menu items", "good" if pos_mapped > 75 else "bad"),
        ("Recipes Loaded", f"{len(b.recipes):,}",
         f"{(b.recipes['recipe_type'] == 'menu_item').sum()} menu items"),
    ])

    theme.section("Checks")
    if q.empty:
        st.success("No issues detected.")
    else:
        for _, r in q.iterrows():
            sev = "opportunity" if r["severity"] == "warning" else "info"
            st.markdown(theme.insight_card(
                sev, f"{r['check']} — {r['count']} found",
                str(r["detail"] or ""), "Review below or adjust source data."),
                unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["Unmapped invoice items",
                                "Unmapped POS items",
                                "All ingredient mappings"])
    with tab1:
        um = b.invoice_map[b.invoice_map["ingredient"].isna()]
        spend = (b.purchases.groupby(["vendor", "item_no"])["extended_price"]
                 .sum().rename("spend"))
        um = um.merge(spend, on=["vendor", "item_no"], how="left")
        um = um.sort_values("spend", ascending=False)
        st.caption("Add rows to `ingredient_map_overrides.csv` "
                   "(columns: item_no, ingredient) then rebuild to fix.")
        st.dataframe(um[["vendor", "item_no", "description", "spend"]]
                     .rename(columns={"vendor": "Vendor", "item_no": "Item #",
                                      "description": "Description",
                                      "spend": "Period Spend"})
                     .style.format({"Period Spend": "${:,.0f}"}),
                     use_container_width=True, hide_index=True, height=380)
    with tab2:
        ump = b.pos_map[b.pos_map["recipe"].isna()].copy()
        sold = b.pos.groupby("item")[["qty_sold", "revenue"]].sum()
        ump = ump.merge(sold, on="item", how="left").sort_values(
            "revenue", ascending=False)
        st.dataframe(ump[["item", "qty_sold", "revenue", "confidence"]]
                     .rename(columns={"item": "POS Item", "qty_sold": "Sold",
                                      "revenue": "Revenue",
                                      "confidence": "Best Match %"})
                     .style.format({"Sold": "{:,.0f}", "Revenue": "${:,.0f}",
                                    "Best Match %": "{:,.0f}"}),
                     use_container_width=True, hide_index=True, height=380)
    with tab3:
        m = b.invoice_map[b.invoice_map["ingredient"].notna()]
        st.dataframe(m[["vendor", "item_no", "description", "ingredient_clean",
                        "confidence", "method"]]
                     .rename(columns={"vendor": "Vendor", "item_no": "Item #",
                                      "description": "Vendor Description",
                                      "ingredient_clean": "Ingredient",
                                      "confidence": "Match %",
                                      "method": "Method"}),
                     use_container_width=True, hide_index=True, height=380)
