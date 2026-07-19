"""Text normalization and fuzzy-matching helpers."""
from __future__ import annotations

import re

from rapidfuzz import fuzz

from foodcost.config import RECIPE_CATEGORY_PREFIXES

_PUNCT_RE = re.compile(r"[^A-Z0-9 ]+")
_WS_RE = re.compile(r"\s+")

# Words that carry no matching signal in vendor descriptions.
STOPWORDS = {
    "THE", "AND", "WITH", "W", "OF", "FRESH", "FRZN", "FROZEN", "RAW", "USDA",
    "GR", "AA", "A", "GRADE", "PREPACK", "CT", "CS", "EA", "PACK", "KEKE",
    "KEKES", "SYS", "CLS", "IMP", "REL", "NAT", "REC",
}


def normalize(text: str) -> str:
    """Uppercase, strip punctuation, collapse whitespace."""
    up = _PUNCT_RE.sub(" ", str(text).upper())
    return _WS_RE.sub(" ", up).strip()


def strip_recipe_category(name: str) -> tuple[str, str]:
    """Split 'DAIRY Cheese American Sliced' -> ('DAIRY', 'Cheese American Sliced')."""
    for prefix in sorted(RECIPE_CATEGORY_PREFIXES, key=len, reverse=True):
        if name.upper().startswith(prefix + " "):
            return prefix, name[len(prefix):].strip()
        if name.upper() == prefix:
            return prefix, name
    return "MISC", name.strip()


# POS ticket-name shorthand -> full words (applied token-wise)
POS_TOKEN_EXPANSIONS = {
    "CHX": "CHICKEN", "CHIX": "CHICKEN", "CHZ": "CHEESE", "CHS": "CHEESE",
    "SAND": "SANDWICH", "SANDW": "SANDWICH", "WAF": "WAFFLE",
    "TURKBAC": "TURKEY BACON", "TURK": "TURKEY", "BAC": "BACON",
    "STRAW": "STRAWBERRY", "BLUE": "BLUEBERRY", "GLAZED": "GLAZE",
    "HF": "HOME FRIES", "OJ": "ORANGE JUICE", "LG": "LARGE", "SM": "SMALL",
    "VEG": "VEGGIE", "PB": "PEANUT BUTTER", "W": "", "WITH": "",
}


def normalize_pos_name(name: str) -> str:
    """Normalize a POS menu-item name for matching against recipe sheets."""
    n = str(name)
    n = re.sub(r"^\(\d+\)\s*", "", n)          # "(1) Apple Cinnamon..." -> "Apple..."
    n = re.sub(r"^(MI|TG|SIDE)\s+", "", n, flags=re.I)
    n = normalize(n)
    tokens = [POS_TOKEN_EXPANSIONS.get(t, t) for t in n.split()]
    return " ".join(t for t in tokens if t)


def token_set_score(a: str, b: str) -> float:
    """Symmetric token-based similarity in [0, 100]."""
    return fuzz.token_set_ratio(normalize(a), normalize(b))


def best_match(query: str, candidates: list[str], cutoff: float = 80.0) -> tuple[str | None, float]:
    """Return the best-scoring candidate above ``cutoff`` (token-set ratio)."""
    best, best_score = None, 0.0
    for cand in candidates:
        score = token_set_score(query, cand)
        if score > best_score:
            best, best_score = cand, score
    if best_score >= cutoff:
        return best, best_score
    return None, best_score
