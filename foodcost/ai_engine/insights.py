"""Deterministic AI-style insight engine.

Generates prioritized, plain-English findings with recommended actions,
the way an experienced restaurant consultant would explain the numbers.
Structured so a real LLM can be layered on later (see ``llm.py``): each
insight carries machine-readable evidence that can be handed to a model
for richer narrative.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from foodcost.config import (
    FOOD_COST_TARGET_PCT, HIGH_FOOD_COST_PCT, MIN_SPEND_FOR_INSIGHT,
    PRICE_SPIKE_PCT, VARIANCE_ALERT_RATIO,
)


@dataclass
class Insight:
    """One prioritized finding."""

    severity: str            # critical | opportunity | positive | info
    title: str
    body: str
    action: str
    impact_dollars: float = 0.0
    tags: list[str] = field(default_factory=list)
    evidence: dict = field(default_factory=dict)


def generate_insights(profit: pd.DataFrame, var: pd.DataFrame,
                      changes: pd.DataFrame, purchases: pd.DataFrame,
                      exploded: pd.DataFrame) -> list[Insight]:
    """Produce a ranked list of insights across all analyses.

    profit  : [recipe, qty_sold, revenue, recipe_cost, gross_profit, food_cost_pct]
    var     : ingredient variance table
    changes : vendor price-change table
    """
    out: list[Insight] = []
    out += _waste_insights(var)
    out += _price_insights(changes, exploded, profit)
    out += _margin_insights(profit)
    out += _positive_insights(profit, var)
    # rank: critical first, then by dollar impact
    order = {"critical": 0, "opportunity": 1, "info": 2, "positive": 3}
    out.sort(key=lambda i: (order.get(i.severity, 9), -abs(i.impact_dollars)))
    return out


# ---------------------------------------------------------------------------
def _waste_insights(var: pd.DataFrame) -> list[Insight]:
    out = []
    if var.empty:
        return out
    flagged = var[(var["variance_ratio"] >= VARIANCE_ALERT_RATIO)
                  & (var["theo_cost"] >= MIN_SPEND_FOR_INSIGHT)]
    for _, r in flagged.head(6).iterrows():
        pct_over = (r["variance_ratio"] - 1) * 100
        out.append(Insight(
            severity="critical" if r["variance_ratio"] >= 1.6 else "opportunity",
            title=f"{r['ingredient_clean']}: purchasing {pct_over:,.0f}% above theoretical usage",
            body=(
                f"You purchased ${r['purchased_dollars']:,.0f} of "
                f"{r['ingredient_clean'].lower()} this period, but POS sales only "
                f"support ${r['theo_cost']:,.0f} of theoretical usage — a gap of "
                f"${r['variance_dollars']:,.0f}. For a "
                f"{r['category'].title()} item this pattern usually means "
                f"spoilage, over-prep, portioning drift, or unrecorded waste."
            ),
            action=(
                "Audit par levels and prep sheets for this ingredient, verify "
                "portioning tools are in use, and check walk-in rotation (FIFO). "
                "Tighten ordering to sales forecast for the next two weeks."
            ),
            impact_dollars=float(r["variance_dollars"]),
            tags=["waste", r["category"]],
            evidence=r.to_dict(),
        ))

    total_waste = var["est_waste_dollars"].sum()
    if total_waste > 500:
        top3 = var.nlargest(3, "est_waste_dollars")
        names = ", ".join(top3["ingredient_clean"].fillna("unknown"))
        out.append(Insight(
            severity="opportunity",
            title=f"Estimated ${total_waste:,.0f} of purchase-vs-usage variance this period",
            body=(
                f"Across all mapped ingredients, purchases exceed theoretical "
                f"usage by ${total_waste:,.0f}. The top three drivers — {names} — "
                f"account for ${top3['est_waste_dollars'].sum():,.0f} "
                f"({top3['est_waste_dollars'].sum() / total_waste * 100:,.0f}%) of "
                "the gap. Some of this is legitimate inventory build, but "
                "recurring gaps of this size typically hide 2-4 points of food cost."
            ),
            action=(
                "Start weekly variance reviews on the top three ingredients "
                "only — small list, big dollars. Recovering half of this gap is "
                f"worth ~${total_waste / 2:,.0f} per period."
            ),
            impact_dollars=float(total_waste),
            tags=["waste", "summary"],
        ))
    return out


# ---------------------------------------------------------------------------
def _price_insights(changes: pd.DataFrame, exploded: pd.DataFrame,
                    profit: pd.DataFrame) -> list[Insight]:
    out = []
    if changes.empty:
        return out
    spikes = changes[(changes["pct_change"] >= PRICE_SPIKE_PCT)
                     & (changes["total_spend"] >= MIN_SPEND_FOR_INSIGHT)]
    for _, r in spikes.head(5).iterrows():
        out.append(Insight(
            severity="critical" if r["pct_change"] >= 15 else "opportunity",
            title=(f"{r['vendor']} price up {r['pct_change']:,.1f}% on "
                   f"{r['description'].title()}"),
            body=(
                f"Case price moved from ${r['first_price']:,.2f} to "
                f"${r['last_price']:,.2f} between "
                f"{r['first_date']:%b %d} and {r['last_date']:%b %d}. "
                f"At this period's volume that added roughly "
                f"${max(r['dollar_impact'], 0):,.0f} of cost."
            ),
            action=(
                f"Ask your {r['vendor']} rep for contract pricing or a "
                "substitute SKU; if the increase holds, reprice the menu items "
                "that use this ingredient or trim the portion."
            ),
            impact_dollars=float(max(r["dollar_impact"], 0)),
            tags=["pricing", r["vendor"]],
            evidence=r.to_dict(),
        ))

    drops = changes[(changes["pct_change"] <= -PRICE_SPIKE_PCT)
                    & (changes["total_spend"] >= MIN_SPEND_FOR_INSIGHT)]
    if not drops.empty:
        best = drops.iloc[-1]
        out.append(Insight(
            severity="positive",
            title=(f"{best['vendor']} price down {abs(best['pct_change']):,.1f}% on "
                   f"{best['description'].title()}"),
            body=(f"Case price fell from ${best['first_price']:,.2f} to "
                  f"${best['last_price']:,.2f} — a tailwind worth "
                  f"~${abs(min(best['dollar_impact'], 0)):,.0f} this period."),
            action="Lock in current pricing if your rep offers a contract window.",
            impact_dollars=float(abs(min(best["dollar_impact"], 0))),
            tags=["pricing"],
        ))
    return out


# ---------------------------------------------------------------------------
def _margin_insights(profit: pd.DataFrame) -> list[Insight]:
    out = []
    if profit.empty:
        return out
    p = profit[profit["revenue"] > 0].copy()
    if p.empty:
        return out
    high_vol = p["qty_sold"] >= p["qty_sold"].quantile(0.75)
    poor = p[high_vol & (p["food_cost_pct"] >= HIGH_FOOD_COST_PCT)]
    for _, r in poor.nlargest(4, "qty_sold").iterrows():
        target_cost = r["revenue"] / r["qty_sold"] * FOOD_COST_TARGET_PCT / 100
        recover = (r["recipe_cost"] - target_cost) * r["qty_sold"]
        out.append(Insight(
            severity="opportunity",
            title=(f"{_pretty(r['recipe'])} sells well but runs "
                   f"{r['food_cost_pct']:,.0f}% food cost"),
            body=(
                f"{r['qty_sold']:,.0f} sold for ${r['revenue']:,.0f} at a plate "
                f"cost of ${r['recipe_cost']:,.2f} — food cost "
                f"{r['food_cost_pct']:,.1f}% vs a {FOOD_COST_TARGET_PCT:,.0f}% "
                "target. High-volume, low-margin items quietly drag the whole "
                "P&L because every additional sale locks in the weak margin."
            ),
            action=(
                f"A ${(target_cost - r['recipe_cost']) * -1:,.2f}/plate cost "
                f"reduction (portion or sourcing) or a price move of "
                f"~${(r['recipe_cost'] / (FOOD_COST_TARGET_PCT / 100)) - (r['revenue'] / r['qty_sold']):,.2f} "
                f"would recover about ${max(recover, 0):,.0f} per period."
            ),
            impact_dollars=float(max(recover, 0)),
            tags=["margin", "menu"],
            evidence=r.to_dict(),
        ))
    return out


# ---------------------------------------------------------------------------
def _positive_insights(profit: pd.DataFrame, var: pd.DataFrame) -> list[Insight]:
    out = []
    if profit.empty:
        return out
    p = profit[(profit["revenue"] > 1000)]
    if not p.empty:
        star = p.nsmallest(1, "food_cost_pct").iloc[0]
        out.append(Insight(
            severity="positive",
            title=(f"{_pretty(star['recipe'])} is your margin workhorse "
                   f"({star['food_cost_pct']:,.1f}% food cost)"),
            body=(f"${star['revenue']:,.0f} of revenue at only "
                  f"${star['recipe_cost']:,.2f} plate cost. Items like this "
                  "fund the rest of the menu."),
            action="Feature it: server suggestion, menu placement, photography.",
            impact_dollars=float(star["gross_profit"]),
            tags=["menu", "positive"],
        ))
    if not var.empty:
        clean = var[(var["theo_cost"] > 500)
                    & (var["variance_ratio"].between(0.85, 1.15))]
        if len(clean) >= 3:
            names = ", ".join(clean.nlargest(3, "theo_cost")["ingredient_clean"])
            out.append(Insight(
                severity="positive",
                title="Several high-volume ingredients are tightly controlled",
                body=(f"{names} all show purchases within ±15% of theoretical "
                      "usage — the kitchen is executing these recipes with "
                      "discipline."),
                action="Use these categories' prep routines as the template "
                       "for the problem ingredients.",
                tags=["waste", "positive"],
            ))
    return out


def _pretty(recipe: str) -> str:
    """'MI Cheese Omelet' -> 'Cheese Omelet'."""
    for prefix in ("MI ", "BATCH ", "PREP ", "YIELD "):
        if recipe.startswith(prefix):
            return recipe[len(prefix):]
    return recipe
