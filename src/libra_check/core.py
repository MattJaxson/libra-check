"""libra-check core: counts in -> LARS v0.1 report (dict) out.

Data model
  unit      one analysis unit = one category dimension (sex, race_ethnicity, intersectional, ...)
            within one rate definition. The comparator is chosen within a unit.
  category  {label, n, k | rate (+ rate_decimals), unknown?}

States (LARS v0.1 §2): determinate_below (U < theta), determinate_at_or_above (L >= theta),
indeterminate (otherwise), not_estimable (comparator rate 0, n = 0, or n below declared min_n).
Interval: two-sided (1 - alpha), i.e. one-sided alpha/2 per bound, so each determinate claim has
error <= alpha/2 (TOST / non-inferiority logic).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

from . import __version__
from .intervals import CITATIONS, METHODS, ZERO_HANDLING, wilson_bounds, z_for
from .power import additional_n_hint, indeterminacy_band
from .provenance import Param, resolve

BELOW, INDET, ABOVE, NE = "determinate_below", "indeterminate", "determinate_at_or_above", "not_estimable"
STATES = (BELOW, INDET, ABOVE, NE)
UNKNOWN_LABELS = {"unknown", "missing/unknown", "missing", "not reported", "declined", "decline to state",
                  "unknown/not reported", "prefer not to say", "na", "n/a", ""}
SCHEMA_VERSION = "libra-audit-report/0.1"
LARS_VERSION = "0.1"
SMALL_N_WARN = 30
UNKNOWN_SHARE_WARN = 0.10


class InputError(ValueError):
    pass


def tkey(t: float) -> str:
    return f"{float(t):g}"


def state_of(lo: float, hi: float, theta: float) -> str:
    if lo is None or hi is None or math.isnan(lo) or math.isnan(hi):
        return NE
    if hi < theta:
        return BELOW
    if lo >= theta:
        return ABOVE
    return INDET


def _software() -> dict:
    commit = None
    try:
        here = Path(__file__).resolve().parent
        commit = subprocess.run(["git", "-C", str(here), "rev-parse", "HEAD"], capture_output=True,
                                text=True, timeout=5).stdout.strip() or None
    except Exception:  # noqa: BLE001
        pass
    return {"name": "libra-check", "version": __version__, "commit": commit}


def _num(x):
    if x is None:
        return None
    if isinstance(x, str):
        x = x.strip()
        if x == "" or x.lower() in ("na", "nan", "none", "null"):
            return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        raise InputError(f"not a number: {x!r}") from None
    return None if math.isnan(v) else v


def _parse_rate(rate_raw, declared):
    """Returns (rate, decimals, decimals_inferred_low). Accepts '0.45', '45%', '45.2%'."""
    if rate_raw is None or (isinstance(rate_raw, str) and rate_raw.strip() == ""):
        return None, None, False
    s = str(rate_raw).strip()
    pct = s.endswith("%")
    if pct:
        s = s[:-1].strip()
    v = _num(s)
    if v is None:
        return None, None, False
    if pct:
        v = v / 100.0
    if declared not in (None, ""):
        return v, int(declared), False
    if "e" in s.lower():
        return v, 6, False
    d = len(s.split(".")[1]) if "." in s else 0
    if pct:
        d += 2
    # conservative: use the decimals actually shown; flag when fewer than 2 (trailing zeros may have been stripped)
    return v, d, d < 2


def prepare_category(c: dict) -> dict:
    label = str(c.get("label", c.get("category", ""))).strip()
    n = _num(c.get("n"))
    if n is None:
        raise InputError(f"category {label!r}: n is required")
    if n < 0 or abs(n - round(n)) > 1e-9:
        raise InputError(f"category {label!r}: n must be a non-negative integer, got {n}")
    n = int(round(n))
    unknown = bool(c.get("unknown")) if c.get("unknown") not in (None, "") else label.lower() in UNKNOWN_LABELS
    if isinstance(c.get("unknown"), str):
        unknown = c["unknown"].strip().lower() in ("1", "true", "yes", "y")
    kraw = _num(c.get("k"))
    rate, dec, dec_low = _parse_rate(c.get("rate"), c.get("rate_decimals"))
    rec = dict(label=label, n=n, unknown=unknown, k_reconstructed=False)
    if kraw is None and rate is None:
        rec.update(k=None, rate=None, k_missing=not unknown)
        return rec
    if kraw is None:
        if not (0 <= rate <= 1):
            raise InputError(f"category {label!r}: rate must be in [0,1], got {rate}")
        h = 0.5 * 10.0 ** (-dec)
        k = int(round(rate * n))
        kmin = int(max(0, math.ceil((rate - h) * n - 1e-9)))
        kmax = int(min(n, math.floor((rate + h) * n + 1e-9)))
        rec.update(k=k, k_reconstructed=True, k_bounds=[min(kmin, k), max(kmax, k)],
                   reconstruction=f"k = round(rate x n) from rate reported to {dec} decimals",
                   decimals_inferred_low=dec_low)
    else:
        k = int(round(kraw))
        if abs(kraw - k) > 1e-9:
            rec.update(k_reconstructed=True, k_bounds=[int(math.floor(kraw)), int(math.ceil(kraw))],
                       reconstruction=f"non-integer k={kraw} rounded")
        rec["k"] = k
    if not (0 <= rec["k"] <= n):
        raise InputError(f"category {label!r}: k={rec['k']} outside [0, n={n}]")
    if c.get("k_bounds") not in (None, ""):
        kb = c["k_bounds"]
        kb = json.loads(kb) if isinstance(kb, str) else kb
        lo_b, hi_b = int(kb[0]), int(kb[1])
        if not (0 <= lo_b <= rec["k"] <= hi_b <= n):
            raise InputError(f"category {label!r}: k_bounds {kb} must satisfy 0 <= lo <= k <= hi <= n")
        rec.update(k_reconstructed=True, k_bounds=[lo_b, hi_b],
                   reconstruction=c.get("reconstruction") or "k range declared in input")
    rec["rate"] = rec["k"] / n if n > 0 else None
    return rec


def _projection(eligible: list[dict], alpha: float) -> dict[str, tuple[float, float]]:
    """Simultaneous (Sidak) Wilson intervals -> bounds on IR_g = p_g / max_h p_h (data-selected max)."""
    G = len(eligible)
    if G < 2:
        return {}
    per = (1 - alpha) ** (1 / G)
    z = float(stats.norm.ppf(1 - (1 - per) / 2))
    k = np.array([c["k"] for c in eligible], float)
    n = np.array([c["n"] for c in eligible], float)
    L, U = wilson_bounds(k, n, z)
    maxU, maxL = float(U.max()), float(L.max())
    out = {}
    for c, lo, hi in zip(eligible, L, U):
        out[c["label"]] = (float(lo) / maxU if maxU > 0 else 0.0,
                           min(1.0, float(hi) / maxL) if maxL > 0 else 1.0)
    return out


def _decision(state: str, burden: str) -> str:
    if state in (BELOW, ABOVE) or burden == "report_only":
        return state
    return f"{state}_burden_on_{'deployer' if burden == 'deployer' else 'challenger'}"


def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def _pair(f, kg, ng, kh, nh, z):
    """Interval for p_g / p_h; degenerate comparator count handled by Wilson-limit division."""
    if kh <= 0:
        lg, _ = wilson_bounds(kg, ng, z)
        _, uh = wilson_bounds(kh, nh, z)
        return (float(lg) / float(uh) if uh > 0 else 0.0), math.inf
    lo, hi = f(kg, ng, kh, nh, z=z)
    return float(lo), float(hi)


def _pairwise_min(f, g, others, alpha, m=1, kg=None, kh=None):
    """Bounds for IR_g = p_g / max_h p_h = min(1, min_h p_g/p_h) over the comparator pool.

    lower = min(1, min_h L(g,h)) at one-sided alpha/(2m): valid without a multiplicity cost, because
            IR_g < lower requires L(g,h*) > p_g/p_h* for the true max h* (one pairwise error).
    upper = min(1, min_h U(g,h)) at one-sided alpha/(2m(G-1)) (Bonferroni over the G-1 pairs), since
            IR_g > upper requires some pairwise upper bound to miss.
    kg / kh: optional count overrides (for the rounding envelope)."""
    if not others:
        return 1.0, 1.0
    z_lo = z_for(alpha, m)
    z_hi = z_for(alpha, m * len(others))
    kg = g["k"] if kg is None else kg
    los, his = [], []
    for h in others:
        khh = h["k"] if kh is None else kh(h)
        los.append(_pair(f, kg, g["n"], khh, h["n"], z_lo)[0])
        his.append(_pair(f, kg, g["n"], khh, h["n"], z_hi)[1])
    return min(1.0, min(los)), min(1.0, min(his))


def analyze(units: list[dict], meta: dict | None = None, *, params: dict[str, Param] | None = None,
            cli: dict | None = None, declared: dict | None = None, preset: str | None = None,
            strict: bool = False, power: float = 0.80, compute_power: bool = True,
            precommitted_hash: str | None = None) -> dict:
    """units: [{"dimension": str, "categories": [ {label, n, k | rate, ...}, ... ]}, ...]
    meta: report context (system, deployer, auditor, decision_point, data_source, data_scope, ...)."""
    meta = dict(meta or {})
    if params is None:
        params = resolve(cli or {}, declared or {}, preset=preset, strict=strict)
    P = {k: v.value for k, v in params.items()}
    thetas, alpha, method = P["thresholds"], float(P["alpha"]), P["interval_method"]
    f = METHODS[method]
    z = z_for(alpha)
    warnings: list[dict] = []

    def warn(code, msg):
        warnings.append({"code": code, "message": msg})

    if not units:
        raise InputError("no analysis units supplied")
    prepared = []
    for u in units:
        cats = []
        for i, c in enumerate(u.get("categories", []), start=1):
            try:
                cats.append(prepare_category(c))
            except InputError as e:
                raise InputError(f"unit {u.get('dimension', 'all')!r}, row {i}: {e}") from None
        labels = [c["label"] for c in cats]
        if len(set(labels)) != len(labels):
            raise InputError(f"unit {u.get('dimension')!r}: duplicate category labels")
        prepared.append(dict(dimension=str(u.get("dimension", "all")), categories=cats))

    min_n = P["min_n"]
    rule = str(P["comparator_rule"])
    fixed = rule.startswith("fixed:")
    adjust = P["selection_adjustment"] if not fixed else "none"

    # ---------- pass 1: categories, exclusion, comparator pool
    n_rows = 0
    for u in prepared:
        cats = u["categories"]
        known = [c for c in cats if not c["unknown"]]
        tot_known = sum(c["n"] for c in known)
        u["total_known_n"] = tot_known
        u["unknown_n"] = sum(c["n"] for c in cats if c["unknown"])
        base = tot_known if P["exclusion_base"] == "known" else tot_known + u["unknown_n"]
        ex = P["small_category_exclusion"]
        for c in cats:
            c["share_of_known"] = (c["n"] / tot_known) if (tot_known > 0 and not c["unknown"]) else None
            c["excluded"], c["exclusion_reason"] = False, None
            if c["unknown"]:
                c["excluded"], c["exclusion_reason"] = True, "unknown category: reported, never in ratios (R4)"
            elif c["n"] == 0:
                c["excluded"], c["exclusion_reason"] = True, "n = 0"
            elif c.get("k_missing"):
                c["excluded"], c["exclusion_reason"] = True, "outcome count (k) not reported; counted in known n"
                warn("MISSING_K", f"unit {u['dimension']}, {c['label']}: n given without k or rate; excluded from ratios")
            elif ex is not None and c["n"] < float(ex) * base:
                c["excluded"] = True
                c["exclusion_reason"] = (f"below {100 * float(ex):g}% of "
                                         f"{'known' if P['exclusion_base'] == 'known' else 'all assessed'} individuals "
                                         f"(declared small_category_exclusion)")
            if c.get("decimals_inferred_low"):
                warn("DECIMALS_INFERRED_LOW", f"unit {u['dimension']}, {c['label']}: rate shown with fewer than 2 decimals; "
                                              f"rounding envelope uses the shown precision (declare rate_decimals if known)")
        elig = [c for c in known if not c["excluded"]]
        below_min = [c for c in elig if min_n is not None and c["n"] < int(min_n)]
        pool_all = elig if rule != "max_rate_all" else [c for c in known if c["n"] > 0 and c["k"] is not None]
        pool = [c for c in pool_all if c not in below_min]          # comparator candidates (min_n applied)
        u["eligible"], u["below_min"], u["pool"] = elig, below_min, pool
        u["comparator_data_selected"] = not fixed
        comp = None
        if fixed:
            name = rule.split(":", 1)[1]
            m = [c for c in elig if c["label"] == name]
            if not m:
                raise InputError(f"unit {u['dimension']!r}: fixed comparator {name!r} not among eligible categories")
            comp = m[0]
        elif pool:
            best = max(c["rate"] for c in pool)
            tied = sorted([c for c in pool if c["rate"] == best], key=lambda c: (-c["n"], c["label"]))
            comp = tied[0]
            if len(tied) > 1:
                warn("TIED_COMPARATOR", f"unit {u['dimension']}: {len(tied)} categories tie for the highest rate; "
                                        f"observed comparator = the largest of them ({comp['label']}); "
                                        f"{'states do not depend on this choice (pairwise_min)' if adjust == 'pairwise_min' else 'conditional states depend on this choice'}")
            if min_n is not None:
                pool_nomin = [c for c in pool_all if c["n"] > 0]
                if pool_nomin:
                    alt = max(pool_nomin, key=lambda c: c["rate"])
                    if alt is not comp and alt["rate"] > comp["rate"]:
                        warn("MIN_N_CHANGES_COMPARATOR", f"unit {u['dimension']}: declared min_n={int(min_n)} removes "
                                                         f"{alt['label']} (n={alt['n']}, highest rate) from the comparator pool")
        else:
            warn("NO_ELIGIBLE_CATEGORIES", f"unit {u['dimension']}: no eligible categories with n >= min_n")
        u["comparator"] = comp
        if comp is not None and comp["k"] == 0:
            warn("ZERO_COMPARATOR", f"unit {u['dimension']}: highest rate is 0; ratios not estimable")
        # rows that receive states
        if adjust == "pairwise_min" and comp is not None:
            u["rows"] = [c for c in elig]                       # every eligible category, comparator included
        else:
            u["rows"] = [c for c in elig if c is not comp]
        n_rows += sum(1 for c in u["rows"] if c not in below_min)
        if u["total_known_n"] > 0 and u["unknown_n"] / (u["unknown_n"] + u["total_known_n"]) >= UNKNOWN_SHARE_WARN:
            warn("UNKNOWN_SHARE_LARGE", f"unit {u['dimension']}: {u['unknown_n']} individuals in unknown categories "
                                        f"(>= {100 * UNKNOWN_SHARE_WARN:g}% of assessed); ratios may not represent them")
        exl = [c["label"] for c in known if c["excluded"] and c["n"] > 0 and not c.get("k_missing")]
        if exl:
            warn("EXCLUDED_CATEGORIES", f"unit {u['dimension']}: excluded {exl}; a justification must be reported "
                                        f"(6 RCNY §5-301(d) where LL144 applies)")

    comparisons = max(n_rows, 1)
    z_adj = z_for(alpha, comparisons)

    # ---------- pass 2: ratios
    out_units = []
    for u in prepared:
        comp = u.get("comparator")
        ratios = []
        proj = {}
        if u["comparator_data_selected"] and comp is not None:
            proj = _projection(u["pool"], alpha)
        for c in (u.get("rows") or []):
            is_comp = c is comp
            r: dict[str, Any] = {"category": c["label"], "n": c["n"], "k": c["k"], "is_comparator": is_comp}
            reasons = []
            if comp is None or comp["k"] == 0:
                reasons.append("comparator rate is 0" if comp is not None else "no comparator")
            if c in u["below_min"]:
                reasons.append(f"n below declared min_n={int(min_n)}")
            point = (c["rate"] / comp["rate"]) if (comp is not None and comp["k"] > 0) else None
            others = [h for h in u["pool"] if h is not c]
            # conditional interval: pair vs the observed (or fixed) comparator
            cond = None
            if point is not None and not is_comp:
                clo, chi = _pair(f, c["k"], c["n"], comp["k"], comp["n"], z)
                calo, cahi = _pair(f, c["k"], c["n"], comp["k"], comp["n"], z_adj)
                cond = (clo, chi, calo, cahi)
            if adjust == "pairwise_min" and point is not None:
                lo, hi = _pairwise_min(f, c, others, alpha)
                alo, ahi = _pairwise_min(f, c, others, alpha, m=comparisons)
                basis = (f"pairwise_min over {len(others)} other categories in the comparator pool "
                         f"(accounts for the data-selected comparator)")
            elif cond is not None:
                lo, hi, alo, ahi = cond
                basis = "pair vs fixed comparator" if fixed else "pair vs observed comparator (conditional; ignores comparator selection)"
            else:
                lo = hi = alo = ahi = None
                basis = None
            r.update(point=None if point is None else round(point, 6),
                     lower=None if lo is None else round(lo, 6),
                     upper=None if hi is None or not np.isfinite(hi) else round(hi, 6),
                     upper_infinite=bool(hi is not None and not np.isfinite(hi)), interval_basis=basis)
            sb, ab, dec, legacy = {}, {}, {}, {}
            for t in thetas:
                s = NE if reasons or lo is None else state_of(lo, hi, t)
                sa = NE if reasons or lo is None else state_of(alo, ahi, t)
                # guard: never issue a determinate state on the opposite side of theta from the point estimate
                for nm, st in (("s", s), ("sa", sa)):
                    if (st == ABOVE and point < t) or (st == BELOW and point >= t):
                        warn("STATE_CONTRADICTS_POINT", f"unit {u['dimension']}, {c['label']}: interval method gave "
                                                        f"{st} with point {point:.3f} at {t:g}; downgraded to indeterminate")
                        if nm == "s":
                            s = INDET
                        else:
                            sa = INDET
                sb[tkey(t)], ab[tkey(t)] = s, sa
                driver = sa if P["multiplicity"] == "bonferroni" else s
                dec[tkey(t)] = _decision(driver, P["burden_rule"])
                legacy[tkey(t)] = None if point is None else ("point_at_or_above" if point >= t else "point_below")
            r["state_by_threshold"] = sb
            r["adjusted_states"] = {"method": f"Bonferroni over {comparisons} comparisons", "state_by_threshold": ab}
            r["decision_by_threshold"] = dec
            r["point_label_by_threshold"] = legacy
            r["not_estimable_reason"] = "; ".join(reasons) or None
            if cond is not None and adjust == "pairwise_min":
                r["conditional"] = {"lower": round(cond[0], 6), "upper": round(cond[1], 6) if np.isfinite(cond[1]) else None,
                                    "state_by_threshold": {tkey(t): (NE if reasons else state_of(cond[0], cond[1], t)) for t in thetas},
                                    "method": "pair vs observed comparator, ignoring that it was selected as the maximum"}
            if c["label"] in proj:
                plo, phi = proj[c["label"]]
                r["projection"] = {"lower": round(plo, 6), "upper": round(phi, 6),
                                   "state_by_threshold": {tkey(t): (NE if reasons else state_of(plo, phi, t)) for t in thetas},
                                   "method": "Sidak-simultaneous Wilson intervals; IR in [L_g/max U, min(1, U_g/max L)]"}
            recon = c.get("k_reconstructed") or (comp is not None and comp.get("k_reconstructed")) or \
                (adjust == "pairwise_min" and any(h.get("k_reconstructed") for h in others))
            if recon and point is not None and lo is not None:
                kb = lambda x, i: x.get("k_bounds", [x["k"], x["k"]])[i]  # noqa: E731
                if adjust == "pairwise_min":
                    elo = _pairwise_min(f, c, others, alpha, kg=kb(c, 0), kh=lambda h: kb(h, 1))[0]
                    ehi = _pairwise_min(f, c, others, alpha, kg=kb(c, 1), kh=lambda h: kb(h, 0))[1]
                else:
                    elo = _pair(f, kb(c, 0), c["n"], kb(comp, 1), comp["n"], z)[0]
                    ehi = _pair(f, kb(c, 1), c["n"], kb(comp, 0), comp["n"], z)[1]
                r["rounding_envelope"] = {"lower": round(elo, 6), "upper": round(ehi, 6) if np.isfinite(ehi) else None,
                                          "state_by_threshold": {tkey(t): (NE if reasons else state_of(elo, ehi, t)) for t in thetas}}
            t0 = thetas[0]
            if compute_power and point is not None and not reasons and not is_comp:
                r["additional_n_hint"] = additional_n_hint(c["k"], c["n"], comp["k"], comp["n"], t0, z, method) \
                    if sb[tkey(t0)] == INDET else None
                r["precision"] = indeterminacy_band(c["n"], comp["n"], comp["rate"], t0, z, method, power=power)
                if r["precision"]:
                    r["precision"]["basis"] = "pair vs observed comparator rate (approximation for pairwise_min states)"
            if c["n"] < SMALL_N_WARN:
                warn("SMALL_N", f"unit {u['dimension']}, {c['label']}: n={c['n']} < {SMALL_N_WARN}")
            if comp is not None and comp["rate"] and comp["rate"] < 0.05 and c["n"] < 200 and not is_comp:
                warn("LOW_RATE_SMALL_N", f"unit {u['dimension']}, {c['label']}: comparator rate {comp['rate']:.3f} with "
                                         f"n={c['n']}; exact error of the interval can exceed nominal (about 8% per "
                                         f"claim vs 5% in red-team enumeration)")
            ratios.append(r)
        cats_out = []
        for c in u["categories"]:
            d = {k: c.get(k) for k in ("label", "n", "k", "rate", "excluded", "exclusion_reason", "unknown",
                                       "share_of_known", "k_reconstructed")}
            if d["rate"] is not None:
                d["rate"] = round(d["rate"], 6)
            if d["share_of_known"] is not None:
                d["share_of_known"] = round(d["share_of_known"], 6)
            if c.get("k_bounds"):
                d["k_bounds"] = c["k_bounds"]
                d["reconstruction"] = c.get("reconstruction")
            cats_out.append(d)
        cp = proj.get(comp["label"]) if comp is not None else None
        out_units.append({
            "dimension": u["dimension"], "total_known_n": u["total_known_n"], "unknown_n": u["unknown_n"],
            "comparator_category": comp["label"] if comp else None,
            "comparator_rate": round(comp["rate"], 6) if comp else None,
            "comparator_data_selected": bool(u.get("comparator_data_selected")),
            "comparator_projection": None if cp is None else
            {"lower": round(cp[0], 6), "upper": round(cp[1], 6), "state_by_threshold": {tkey(t): state_of(cp[0], cp[1], t) for t in thetas}},
            "categories": cats_out, "ratios": ratios})

    # ---------- warnings about parameters, method and data
    undeclared = [p.name for p in params.values() if p.value == "UNDECLARED"]
    defaults = [p.name for p in params.values() if p.role == "tool_default" and p.value != "UNDECLARED"]
    unattr = [p.name for p in params.values() if p.role == "unattributed"]
    if undeclared:
        warn("UNDECLARED_PARAMETERS", f"not declared: {undeclared}")
    if defaults:
        warn("TOOL_DEFAULT_PARAMETERS", f"set by libra-check default, not by an accountable party: {defaults}")
    if unattr:
        warn("UNATTRIBUTED_PARAMETERS", f"values supplied without a setter: {unattr}")
    if params["burden_rule"].role in ("tool_default", "unattributed"):
        warn("NO_BURDEN_RULE_ASSIGNED", "no accountable party assigned a burden rule: indeterminate results are unresolved, not passes")
    if method == "katz_log":
        warn("ANTICONSERVATIVE_METHOD", "katz_log can exceed nominal error in the direction of false 'at or above' "
                                        "(up to ~15% vs 5% per claim at small n / low rates); use for sensitivity only")
    if adjust == "none" and not fixed:
        warn("CONDITIONAL_ON_SELECTED_COMPARATOR", "selection_adjustment = none: states treat the data-selected comparator "
                                                   "as fixed; per-claim error can exceed nominal with many categories")
    if any(c.get("k_reconstructed") for u in out_units for c in u["categories"]):
        warn("RECONSTRUCTED_COUNTS", "some k were reconstructed from rounded rates; see rounding_envelope")
    ds = str(meta.get("data_source", "unknown")).lower()
    if ds in ("test", "synthetic"):
        warn("TEST_OR_SYNTHETIC_DATA", f"data_source = {ds}: results do not describe the system's real use (R17)")
    scope = str(meta.get("data_scope", "own"))
    if scope.startswith("pooled"):
        warn("POOLED_DATA", f"data_scope = {scope}: rates pool several deployers; the impact ratio is not this "
                            f"deployer's own impact ratio")
    if P["estimand"] == "finite_population":
        warn("FINITE_POPULATION_ESTIMAND", "declared estimand = finite_population: the point IR is exact for the "
                                           "audited window; states describe the underlying process (inferential view)")
    t0 = tkey(thetas[0])
    for u in out_units:
        for r in u["ratios"]:
            s = r["state_by_threshold"][t0]
            if "rounding_envelope" in r and r["rounding_envelope"]["state_by_threshold"][t0] != s:
                warn("ROUNDING_CHANGES_STATE", f"unit {u['dimension']}, {r['category']}: count reconstruction "
                                               f"uncertainty changes the state at {t0}")
            if "conditional" in r and r["conditional"]["state_by_threshold"][t0] != s:
                warn("SELECTION_CHANGES_STATE", f"unit {u['dimension']}, {r['category']}: ignoring comparator selection "
                                                f"would give {r['conditional']['state_by_threshold'][t0]} at {t0}")
    for k in ("ll144_derivation",):
        info = meta.get(k) or {}
        if info.get("n_missing_score"):
            warn("MISSING_SCORES", f"{info['n_missing_score']} rows had no numeric score and are not counted in any n")

    # ---------- summary
    allr = [r for u in out_units for r in u["ratios"]]
    summ: dict[str, Any] = {"units": len(out_units), "comparisons_count": n_rows, "by_threshold": {}}
    for t in thetas:
        k = tkey(t)
        cnt = {s: sum(r["state_by_threshold"][k] == s for r in allr) for s in STATES}
        acnt = {s: sum(r["adjusted_states"]["state_by_threshold"][k] == s for r in allr) for s in STATES}
        summ["by_threshold"][k] = {
            "states": cnt, "adjusted_states": acnt,
            "any_determinate_below": cnt[BELOW] > 0,
            "all_determinate_at_or_above": bool(allr) and cnt[ABOVE] == len(allr),
            "familywise_any_determinate_below": acnt[BELOW] > 0,
            "familywise_all_determinate_at_or_above": bool(allr) and acnt[ABOVE] == len(allr),
            "point_below_count": sum(r["point_label_by_threshold"][k] == "point_below" for r in allr)}

    plist = [p.as_dict() for p in params.values()]
    input_hash = _hash(units)
    params_hash = params_sha256(params)
    pre = None
    if precommitted_hash:
        pre = {"hash": precommitted_hash, "matches": precommitted_hash == params_hash,
               "note": "a match shows the parameter values equal those committed; it shows the commitment predates the "
                       "data only if the hash was published (time-stamped) before the data were seen"}
        if not pre["matches"]:
            warn("PRECOMMITMENT_MISMATCH", "declared parameter values differ from the pre-committed hash")
    rep = {
        "schema_version": SCHEMA_VERSION, "lars_version": LARS_VERSION,
        "report_id": f"lc-{_hash([input_hash, params_hash])[:16]}",
        "generated_at": meta.pop("generated_at", None) or _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "system": meta.get("system"), "deployer": meta.get("deployer"), "auditor": meta.get("auditor"),
        "decision_point": meta.get("decision_point"),
        "outcome_definition": P["outcome_definition"],
        "selection_rule": P["selection_rule"], "score_cut": P["score_cut"],
        "category_scheme": P["category_scheme"],
        "data_window": P["data_window"], "data_source": meta.get("data_source", "unknown"),
        "data_scope": scope, "estimand": P["estimand"],
        "unknown_category_handling": P["unknown_category_handling"],
        "comparator_rule": P["comparator_rule"], "selection_adjustment": adjust,
        "exclusion_base": P["exclusion_base"],
        "thresholds": thetas, "alpha": alpha, "alpha_per_bound": alpha / 2,
        "interval_method": method, "interval_citation": CITATIONS[method], "zero_handling": ZERO_HANDLING[method],
        "min_n": min_n, "burden_rule": P["burden_rule"], "multiplicity": P["multiplicity"],
        "comparisons_count": n_rows,
        "units": out_units, "parameters": plist, "summary": summ, "warnings": warnings,
        "software": _software(), "input_sha256": input_hash, "parameters_sha256": params_hash,
        "precommitment": pre,
    }
    return rep


def params_sha256(params: dict[str, Param]) -> str:
    return _hash({p.name: p.value for p in params.values()})
