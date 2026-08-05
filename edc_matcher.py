"""
edc_matcher.py
Matches ingredient text (from OCR or manual entry) against the Shero EDC
database. Tries an exact/alias match first, then falls back to fuzzy string
matching so misspellings, spacing, and naming variants ("Bisphenol-A",
"bisphenolA", "BPA") still resolve to the right entry.
"""
 
import json
import re
from rapidfuzz import fuzz, process
 
# fuzz.ratio compares whole strings letter-by-letter (Levenshtein-based).
# We deliberately avoid WRatio/token_sort here: those score two ingredients
# as "similar" just because they share a common word like "acid" or "-ol",
# which caused false positives (e.g. "Citric Acid" matching "Perfluorooctanoic
# Acid"). fuzz.ratio only cares about overall string similarity, so it's a
# much safer default for telling unrelated chemicals apart.
FUZZY_SCORER = fuzz.ratio
FUZZY_THRESHOLD = 90  # 0-100 similarity score; raise to be stricter
 
# A short list of extremely common, well-established safe ingredients that
# should never be flagged, no matter what a fuzzy match thinks it sees.
# This is a safety net on top of the stricter matching above — not a
# substitute for it.
SAFE_INGREDIENTS = {
    "water", "aqua", "eau",
    "citric acid", "ascorbic acid", "vitamin c",
    "tocopherol", "vitamin e", "tocopheryl acetate",
    "glycerin", "glycerol", "glycerine",
    "sodium chloride", "salt", "sugar", "sucrose",
    "xanthan gum", "guar gum",
    "sodium bicarbonate", "baking soda",
    "aloe vera", "aloe barbadensis leaf juice",
    "panthenol", "niacinamide", "hyaluronic acid",
    "lactic acid", "malic acid",
    "beeswax", "cera alba",
    "sodium benzoate", "ins 211", "e211",
    "potassium sorbate", "ins 202", "e202",
    "calcium propionate", "ins 282", "e282",
}
 
 
def load_database(path="edc_database.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
 
 
def _build_lookup(database):
    """Map every known name/alias (lowercased) -> canonical database key."""
    lookup = {}
    for key, entry in database.items():
        names = [key] + entry.get("aliases", [])
        for name in names:
            lookup[str(name).strip().lower()] = key
    return lookup
 
 
def split_ingredients(raw_text):
    """Turn raw OCR/pasted text into a clean list of individual ingredients."""
    text = raw_text.replace("\n", ",")
    text = re.sub(r"[•·*]", ",", text)
    parts = [p.strip(" .;-") for p in text.split(",")]
    return [p for p in parts if p and len(p) > 1]
 
 
def match_ingredients(ingredient_list, database):
    """
    For each ingredient string, try an exact/alias match, then a fuzzy match.
    Returns a list of dicts: {ingredient, matched_key, score, entry}
    """
    lookup = _build_lookup(database)
    choices = list(lookup.keys())
 
    results = []
    for ingredient in ingredient_list:
        norm = ingredient.strip().lower()
        if not norm:
            continue
 
        # 0. Known-safe ingredient — never flag, regardless of what fuzzy
        #    matching thinks it sees.
        if norm in SAFE_INGREDIENTS:
            continue
 
        # 1. Exact / alias match
        if norm in lookup:
            key = lookup[norm]
            results.append({
                "ingredient": ingredient,
                "matched_key": key,
                "score": 100,
                "entry": database[key],
            })
            continue
 
        # 2. Fuzzy match — only for ingredients close enough in both content
        #    AND length to plausibly be a typo/variant of the same name.
        match = process.extractOne(norm, choices, scorer=FUZZY_SCORER)
        if match:
            matched_name, score, _ = match
            length_ratio = min(len(norm), len(matched_name)) / max(len(norm), len(matched_name))
            if score >= FUZZY_THRESHOLD and length_ratio >= 0.7:
                key = lookup[matched_name]
                results.append({
                    "ingredient": ingredient,
                    "matched_key": key,
                    "score": round(score, 1),
                    "entry": database[key],
                })
 
    return results
 
 
def summarize_risk(matches):
    """Counts of flagged ingredients by risk level, for a dashboard summary."""
    counts = {"High": 0, "Medium-High": 0, "Medium": 0, "Low": 0}
    for m in matches:
        level = m["entry"].get("risk_level", "Unknown")
        counts[level] = counts.get(level, 0) + 1
    return counts
