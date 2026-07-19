"""Waste & variance intelligence page."""
from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from foodcost.costing.variance import category_variance
from ui import theme
from ui.theme import fmt_money


def render(b) -> None:
    theme.hero("Waste & Variance Intelligence",
               "Purchases vs POS-driven theoretical usage. Persistent gaps = "
               "spoilage, over-prep, portioning drift or shrinkage.",
               "WASTE RADAR")

    var = b.variance[b.variance["ingredient_clean"].notna()].copy()
    mapped = var[var["theo_cost"] > 0]

    total_gap = var["est_waste_dollars"].sum()
    rev = b.pos["revenue"].sum()
    theme.metric_row([
        ("Est. Waste / Variance", fmt_money(total_gap),
         f"{total_gap / rev * 100 if rev else 0:,.1f}% of sales", "bad"),
        ("Ingredients Over 130%", f"{(mapped['variance_ratio'] > 1.3).sum():,}",
         "of theoretical usage", "bad"),
        ("Well-Controlled", f"{mapped['variance_ratio'].between(0.85, 1.15).sum():,}",
         "within ±15%", "good"),
        ("Highest-Risk Category",
         var.groupby('category')['est_waste_dollars'].sum().idxmax()
         if not var.empty else "—"),
    ])

    # ---------------- variance scatter ----------------
    theme.section("Variance Map",
                  "right of the line = buying more than sales justify · "
                  "bubble = purchase $")
    v = mapped[(mapped["purchased_dollars"] > 50)].copy()
    if not v.empty:
        v = v[v["variance_ratio"] < 8]
        fig = px.scatter(
            v, x="variance_ratio", y="waste_risk",
            size="purchased_dollars", color="category",
            hover_name="ingredient_clean",
            color_discrete_map=theme.CATEGORY_COLORS,
            labels={"variance_ratio": "purchased ÷ theoretical",
                    "waste_risk": "waste risk score"},
            size_max=45)
        fig.add_vline(x=1.0, line_color=theme.ACCENT, line_width=2)
        fig.add_vrect(x0=1.3, x1=min(8, max(2.0, v["variance_ratio"].max())),
                      fillcolor="rgba(192,57,43,0.05)", line_width=0)
        fig.update_layout(height=430)
        st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns([1, 1])
    with c1:
        theme.section("Waste $ by Category")
        cat = category_variance(var)
        cat = cat[cat["est_waste_dollars"] > 0]
        fig = px.bar(cat.sort_values("est_waste_dollars"),
                     x="est_waste_dollars", y="category", orientation="h",
                     color="category", color_discrete_map=theme.CATEGORY_COLORS,
                     labels={"est_waste_dollars": "estimated waste ($)",
                             "category": ""})
        fig.update_layout(height=330, showlegend=False, xaxis_tickprefix="$")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        theme.section("Top Dollar Gaps", "purchased minus theoretical")
        top = var.nlargest(9, "est_waste_dollars")
        fig = go.Figure(go.Bar(
            x=top["est_waste_dollars"], y=top["ingredient_clean"],
            orientation="h", marker_color=theme.RED,
            text=[f"${x:,.0f}" for x in top["est_waste_dollars"]],
            textposition="outside"))
        fig.update_layout(height=330, xaxis_tickprefix="$",
                          yaxis=dict(autorange="reversed"),
                          xaxis_range=[0, top["est_waste_dollars"].max() * 1.25])
        st.plotly_chart(fig, use_container_width=True)

    # ---------------- likely causes ----------------
    theme.section("Diagnosis & Recommended Actions")
    causes = {
        "Purchasing far exceeds usage": (
            "Over-ordering vs sales pace, spoilage, or unrecorded waste",
            "Cut pars, tighten FIFO rotation, log waste for 2 weeks"),
        "Over-purchasing": (
            "Par levels set above true demand; possible over-prep",
            "Rebuild pars from theoretical usage + 10% buffer"),
        "No theoretical usage (unmapped or unsold)": (
            "Item bought but no recipe uses it (or mapping gap)",
            "Verify mapping on the Data Quality page; delist dead stock"),
        "Purchases below usage (stock draw-down or under-portioning)": (
            "Running down inventory, or portions smaller than recipe",
            "Spot-check portioning; confirm opening inventory levels"),
    }
    flagged = var[var["flag"] != "In line"]
    for flag, group in flagged.groupby("flag"):
        if flag not in causes:
            continue
        why, action = causes[flag]
        names = ", ".join(group.nlargest(5, "purchased_dollars")["ingredient_clean"])
        dollars = group["est_waste_dollars"].sum()
        st.markdown(theme.insight_card(
            "critical" if dollars > 2000 else "opportunity",
            f"{flag} — {len(group)} ingredients",
            f"<b>Most significant:</b> {names}.<br><b>Likely causes:</b> {why}.",
            action, dollars), unsafe_allow_html=True)

    theme.section("Full Variance Table")
    show = var[["ingredient_clean", "category", "purchased_dollars", "theo_cost",
                "variance_dollars", "variance_ratio", "waste_risk", "flag"]]
    show = show.rename(columns={
        "ingredient_clean": "Ingredient", "category": "Category",
        "purchased_dollars": "Purchased $", "theo_cost": "Theoretical $",
        "variance_dollars": "Variance $", "variance_ratio": "Ratio",
        "waste_risk": "Risk", "flag": "Flag"})
    st.dataframe(
        show.style.format({"Purchased $": "${:,.0f}", "Theoretical $": "${:,.0f}",
                           "Variance $": "${:,.0f}", "Ratio": "{:,.2f}",
                           "Risk": "{:,.0f}"})
        .background_gradient(subset=["Risk"], cmap="Reds", vmin=0, vmax=100),
        use_container_width=True, hide_index=True, height=480)
