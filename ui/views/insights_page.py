"""AI insight engine page."""
from __future__ import annotations

import streamlit as st

from foodcost.ai_engine import llm
from foodcost.ai_engine.insights import generate_insights
from ui import theme


def render(b) -> None:
    theme.hero("AI Insight Engine",
               "The numbers, explained like a seasoned operations consultant — "
               "prioritized by dollar impact.", "INSIGHTS")

    if "insights" not in st.session_state:
        with st.spinner("Analyzing your period…"):
            st.session_state["insights"] = generate_insights(
                b.profit, b.variance, b.price_changes, b.purchases, b.exploded)
    insights = st.session_state["insights"]

    llm_on = llm.is_available()
    c1, c2 = st.columns([3, 1])
    with c1:
        kinds = ["critical", "opportunity", "positive", "info"]
        counts = {k: sum(1 for i in insights if i.severity == k) for k in kinds}
        st.markdown(
            " ".join(f'<span class="pill {c}">{counts[k]} {k}</span>'
                     for k, c in zip(kinds, ["red", "gold", "green", "gray"])),
            unsafe_allow_html=True)
    with c2:
        st.caption("LLM narrative: " +
                   ("**on** (Claude)" if llm_on else
                    "off — set `ANTHROPIC_API_KEY` to enable. "
                    "Deterministic engine active."))

    total_impact = sum(i.impact_dollars for i in insights
                       if i.severity in ("critical", "opportunity"))
    st.markdown(theme.insight_card(
        "info", f"Identified opportunity: ≈ ${total_impact:,.0f} this period",
        "Sum of the dollar impact across all critical findings and "
        "opportunities below. Not all of it is recoverable, but the top "
        "three actions typically capture 40–60% within two periods.",
        "Work the list top-down — it is sorted by severity and dollars."),
        unsafe_allow_html=True)

    tab_all, tab_waste, tab_price, tab_menu = st.tabs(
        ["All findings", "Waste", "Pricing", "Menu"])
    with tab_all:
        _render_list(insights)
    with tab_waste:
        _render_list([i for i in insights if "waste" in i.tags])
    with tab_price:
        _render_list([i for i in insights if "pricing" in i.tags])
    with tab_menu:
        _render_list([i for i in insights if "menu" in i.tags or "margin" in i.tags])


def _render_list(items) -> None:
    if not items:
        st.caption("No findings in this category.")
        return
    for ins in items:
        st.markdown(theme.insight_card(
            ins.severity, ins.title, ins.body, ins.action, ins.impact_dollars),
            unsafe_allow_html=True)
