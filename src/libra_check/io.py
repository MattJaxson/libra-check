"""Input loading: aggregate counts (CSV/JSON) and individual-level LL144 data (CSV)."""
from __future__ import annotations

import csv
import json
import math
import statistics
from collections import OrderedDict
from pathlib import Path

from .core import UNKNOWN_LABELS, InputError

ALIASES = {
    "category": ["category", "label", "group", "category_label"],
    "n": ["n", "applicants", "number_of_applications", "num_applicants", "number_of_applicants", "total", "assessed"],
    "k": ["k", "selected", "n_selected", "number_selected", "n_selected_or_n_above_median", "above_median",
          "n_above_median"],
    "rate": ["rate", "selection_rate", "scoring_rate", "result"],
    "rate_decimals": ["rate_decimals"],
    "unknown": ["unknown"],
    "dimension": ["dimension", "characteristic", "protected_char_group"],
}

TRUE = {"1", "true", "yes", "y", "t", "selected", "advanced"}
FALSE = {"0", "false", "no", "n", "f", "rejected", "not selected"}


def load_counts(path: str | Path) -> tuple[list[dict], dict]:
    """CSV columns: category (or label), n, k and/or rate [, rate_decimals, unknown, dimension].
    JSON: {"meta": {...}, "units": [{"dimension", "categories": [...]}]} or {"categories": [...]} or [...]."""
    p = Path(path)
    if p.suffix.lower() == ".json":
        raw = json.loads(p.read_text())
        meta = {}
        if isinstance(raw, dict):
            meta = raw.get("meta", {})
            if "units" in raw:
                return raw["units"], meta
            if "categories" in raw:
                return [{"dimension": raw.get("dimension", "all"), "categories": raw["categories"]}], meta
        if isinstance(raw, list):
            return [{"dimension": "all", "categories": raw}], meta
        raise InputError("unrecognised JSON counts layout")
    with p.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise InputError("empty counts file")
    raw_cols = {c.strip().lower().replace(" ", "_"): c for c in rows[0].keys()}
    cols = {}
    for canon, names in ALIASES.items():
        for nm in names:
            if nm in raw_cols:
                cols[canon] = raw_cols[nm]
                break
    lab = cols.get("category")
    if lab is None or "n" not in cols or ("k" not in cols and "rate" not in cols):
        raise InputError(f"counts CSV needs a category column ({ALIASES['category']}), an n column ({ALIASES['n']}) "
                         f"and k ({ALIASES['k']}) and/or rate ({ALIASES['rate']}); got {list(rows[0])}")
    units: "OrderedDict[str, list]" = OrderedDict()
    for r in rows:
        dim = r.get(cols["dimension"], "all").strip() if "dimension" in cols else "all"
        c = {"label": r[lab], "n": r[cols["n"]]}
        for key in ("k", "rate", "rate_decimals", "unknown"):
            if key in cols and r[cols[key]] not in (None, ""):
                c[key] = r[cols[key]]
        units.setdefault(dim or "all", []).append(c)
    return [{"dimension": d, "categories": cs} for d, cs in units.items()], {}


def _truthy(v: str, rowno: int) -> bool:
    s = str(v).strip().lower()
    if s in TRUE:
        return True
    if s in FALSE:
        return False
    raise InputError(f"row {rowno}: cannot read selection value {v!r}")


def load_individuals(path: str | Path, sex_col: str | None = "sex", race_col: str | None = "race",
                     selected_col: str | None = None, score_col: str | None = None,
                     unknown_values: set[str] | None = None, intersectional: bool = True) -> tuple[list[dict], dict]:
    """Individual-level data -> counts per LL144 (6 RCNY §5-300, §5-301).

    Selection tools: k = individuals selected / advanced.
    Scoring tools:   k = individuals scoring ABOVE the median of the FULL sample of applicants
                     (§5-301(c)(1)), including those in unknown categories. Ties at the median are not
                     'above' and are counted in the info block.
    Unknown categories are reported (count) and never enter a ratio."""
    if (selected_col is None) == (score_col is None):
        raise InputError("give exactly one of selected_col / score_col")
    unk = {u.lower() for u in (unknown_values or UNKNOWN_LABELS)}
    with Path(path).open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise InputError("empty file")
    for col in (sex_col, race_col, selected_col, score_col):
        if col and col not in rows[0]:
            raise InputError(f"column {col!r} not in file (have {list(rows[0])})")
    info: dict = {"n_rows": len(rows)}
    if score_col:
        scores = []
        missing = 0
        for r in rows:
            try:
                v = float(r[score_col])
                if math.isnan(v):
                    raise ValueError
                scores.append(v)
            except (TypeError, ValueError):
                missing += 1
        if not scores:
            raise InputError("no numeric scores")
        med = statistics.median(scores)
        info.update(score_cut="median_full_sample", median=med, n_scored=len(scores), n_missing_score=missing,
                    ties_at_median=sum(1 for s in scores if s == med))

    def norm(v):
        s = (v or "").strip()
        return "Unknown" if s.lower() in unk else s

    dims = []
    if sex_col:
        dims.append(("sex", lambda r: norm(r[sex_col])))
    if race_col:
        dims.append(("race_ethnicity", lambda r: norm(r[race_col])))
    if intersectional and sex_col and race_col:
        def inter(r):
            a, b = norm(r[race_col]), norm(r[sex_col])
            return "Unknown" if "Unknown" in (a, b) else f"{a} / {b}"
        dims.append(("intersectional", inter))
    alt = score_col is not None and info.get("ties_at_median", 0) > 0
    units, alt_units = [], []
    for dim, key in dims:
        counts: "OrderedDict[str, list[int]]" = OrderedDict()
        alt_k: dict[str, int] = {}
        for i, r in enumerate(rows, start=2):
            if score_col:
                try:
                    v = float(r[score_col])
                except (TypeError, ValueError):
                    continue
                hit = v > info["median"]
                alt_k[key(r)] = alt_k.get(key(r), 0) + int(v >= info["median"])
            else:
                hit = _truthy(r[selected_col], i)
            c = counts.setdefault(key(r), [0, 0])
            c[0] += 1
            c[1] += int(hit)
        cats = [{"label": lab, "n": n, "k": k, "unknown": lab == "Unknown"} for lab, (n, k) in
                sorted(counts.items(), key=lambda kv: (kv[0] == "Unknown", kv[0]))]
        units.append({"dimension": dim, "categories": cats})
        if alt:
            alt_units.append({"dimension": dim, "categories": [dict(c, k=alt_k.get(c["label"], 0)) for c in cats]})
    if alt:
        info["alt_cut"] = "score >= median (adjacent cut, used to test cut stability)"
        info["_alt_units"] = alt_units
    return units, info
