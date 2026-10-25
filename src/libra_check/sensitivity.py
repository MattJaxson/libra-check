"""Forking-paths view: states for every category across a grid of defensible parameter choices.

If a category's verdict changes across the grid, the verdict depends on a governance choice, and the
provenance record for that choice carries the weight. This makes threshold/method shopping visible.
"""
from __future__ import annotations

import itertools
from collections import Counter, defaultdict

from .core import analyze

GRID = {
    "thresholds": [[0.8], [0.85], [0.9]],
    "alpha": [0.10, 0.05],
    "interval_method": ["mover_wilson", "koopman", "miettinen_nurminen"],
    "selection_adjustment": ["pairwise_min", "none"],
    "small_category_exclusion": [None, 0.02],
    "multiplicity": ["none", "bonferroni"],
}


def grid(units, meta=None, grid_spec=None):
    spec = grid_spec or GRID
    keys = list(spec)
    per_cat: dict[tuple, Counter] = defaultdict(Counter)
    configs = 0
    for combo in itertools.product(*(spec[k] for k in keys)):
        cli = dict(zip(keys, combo))
        rep = analyze(units, meta or {}, cli=cli, compute_power=False)
        configs += 1
        t = f"{cli['thresholds'][0]:g}"
        for u in rep["units"]:
            for r in u["ratios"]:
                st = (r["adjusted_states"] if cli["multiplicity"] == "bonferroni" else r)["state_by_threshold"][t]
                per_cat[(u["dimension"], r["category"])][(t, st)] += 1
    out = []
    for (dim, cat), cnt in per_cat.items():
        by_t = defaultdict(dict)
        for (t, st), v in cnt.items():
            by_t[t][st] = v
        stable = all(len(v) == 1 for v in by_t.values())
        out.append({"dimension": dim, "category": cat, "verdict_stable_within_each_threshold": stable,
                    "states_by_threshold": dict(by_t)})
    return {"configurations": configs, "grid": {k: [str(x) for x in v] for k, v in spec.items()}, "categories": out}


def to_text(res):
    L = [f"{res['configurations']} parameter configurations (grid: {', '.join(res['grid'])})"]
    for c in res["categories"]:
        flag = "stable" if c["verdict_stable_within_each_threshold"] else "DEPENDS ON CHOICES"
        parts = []
        for t, d in sorted(c["states_by_threshold"].items()):
            parts.append(f"θ={t}: " + ", ".join(f"{k.replace('determinate_', '')} {v}" for k, v in sorted(d.items())))
        L.append(f"  {c['dimension']} / {c['category']}: {flag} | " + " | ".join(parts))
    return "\n".join(L)
