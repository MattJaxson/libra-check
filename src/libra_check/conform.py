"""LARS v0.1 §7 conformance checker: report JSON -> pass/fail per MUST item.

Works on any JSON report using the LARS field names, not only reports made by libra-check.
"""
from __future__ import annotations

import re

GOVERNANCE = ("thresholds", "alpha", "interval_method", "comparator_rule", "outcome_definition",
              "category_scheme", "min_n", "small_category_exclusion", "unknown_category_handling",
              "data_window", "burden_rule")
STATES = {"determinate_below", "indeterminate", "determinate_at_or_above", "not_estimable"}
FORBIDDEN = re.compile(r"\b(pass(ed|es)?|compliant|fail(ed|s)?|no adverse impact)\b", re.I)


def _units(rep):
    if "units" in rep:
        return rep["units"]
    return [{"categories": rep.get("categories", []), "ratios": rep.get("ratios", []),
             "comparator_category": rep.get("comparator_category")}]


def check(rep: dict) -> dict:
    res = []

    def add(no, req, name, ok, detail="", status=None):
        res.append({"check": no, "requirement": req, "name": name, "pass": bool(ok), "detail": detail,
                    "status": status or ("pass" if ok else "fail")})

    units = _units(rep)
    cats = [c for u in units for c in u.get("categories", [])]
    ratios = [r for u in units for r in u.get("ratios", [])]
    miss = [c.get("label") for c in cats if c.get("n") is None or (c.get("k") is None and not c.get("unknown"))]
    has_unknown_count = all("unknown_n" in u for u in units) or any(c.get("unknown") for c in cats)
    add(1, "R1", "n and k for every category incl. excluded and unknown", cats and not miss and has_unknown_count,
        f"missing n/k: {miss}" if miss else ("" if has_unknown_count else "unknown-category count not reported"))
    add(2, "R2", "outcome definition + decision point", bool(rep.get("outcome_definition"))
        and rep.get("outcome_definition") != "UNDECLARED" and bool(rep.get("decision_point")),
        f"outcome_definition={rep.get('outcome_definition')!r}, decision_point={rep.get('decision_point')!r}")
    add(3, "R3", "comparator rule + category named; data-driven choice flagged",
        bool(rep.get("comparator_rule")) and all(u.get("comparator_category") for u in units)
        and all("comparator_data_selected" in u for u in units if "units" in rep))
    unk = {c.get("label") for c in cats if c.get("unknown")}
    bad = [u.get("comparator_category") for u in units if u.get("comparator_category") in unk] + \
          [r.get("category") for r in ratios if r.get("category") in unk]
    add(4, "R4", "unknown category kept out of comparator and ratios", not bad, f"offending: {bad}" if bad else "")
    est = [r for r in ratios if r.get("point") is not None]
    add(5, "R5", "point IR for each estimable category", all(isinstance(r["point"], (int, float)) for r in est) and
        all(r.get("point") is not None for r in ratios if (r.get("state_by_threshold") or {}) and
            set(r["state_by_threshold"].values()) - {"not_estimable"}))
    add(6, "R6", "interval + alpha for each estimable IR", rep.get("alpha") is not None and
        all(r.get("lower") is not None and (r.get("upper") is not None or r.get("upper_infinite")) for r in est))
    add(7, "R7", "interval method named with citation; zero handling stated",
        bool(rep.get("interval_method")) and bool(rep.get("interval_citation")) and bool(rep.get("zero_handling")))
    th = [f"{float(t):g}" for t in rep.get("thresholds", [])]
    ok8 = bool(th) and all(set(r.get("state_by_threshold", {})) >= set(th) and
                           set(r["state_by_threshold"].values()) <= STATES for r in ratios)
    add(8, "R8", "four-valued state per category per threshold; theta disclosed", ok8)
    words = []
    for r in ratios:
        for k, v in (r.get("decision_by_threshold") or {}).items():
            if r.get("state_by_threshold", {}).get(k) == "indeterminate" and FORBIDDEN.search(str(v)):
                words.append((r.get("category"), v))
    add(9, "R9", "no pass/compliant/fail wording on indeterminate; burden rule + setter stated",
        not words and bool(rep.get("burden_rule")) and _setter(rep, "burden_rule"), f"{words}" if words else "")
    params = {p.get("name"): p for p in rep.get("parameters", [])}
    need = ("name", "value", "set_by", "role", "process", "date", "source")
    missing = [g for g in GOVERNANCE if g not in params]
    incomplete = [g for g in GOVERNANCE if g in params and any(k not in params[g] for k in need)]
    add(10, "R13", "provenance record for every governance parameter", not missing and not incomplete,
        f"missing: {missing}; incomplete: {incomplete}" if (missing or incomplete) else "")
    nosrc = [g for g in GOVERNANCE if g in params and not params[g].get("source")]
    add(11, "R14", "legal source cited or 'unassigned by rule' stated", not nosrc, f"no source: {nosrc}" if nosrc else "")
    pre = rep.get("precommitment") or {}
    changed = [g for g, p in params.items() if p.get("changed_from") is not None]
    if pre.get("matches"):
        add(12, "R15", "post-hoc parameter changes disclosed", True,
            f"parameter values match pre-committed hash; disclosed changes: {changed}", status="verified_against_commitment")
    else:
        add(12, "R15", "post-hoc parameter changes disclosed", True,
            f"UNVERIFIABLE: no matching pre-committed parameter hash; self-declared changes: {changed}",
            status="unverifiable")
    sw = rep.get("software") or {}
    add(13, "R16", "software + version", bool(sw.get("name")) and bool(sw.get("version")))
    ds = str(rep.get("data_source", "")).lower()
    add(14, "R17", "test/synthetic data flagged", ds in ("historical", "test", "synthetic"),
        f"data_source={ds!r} (must be historical, test or synthetic)")
    accountable = [g for g in GOVERNANCE if g in params and params[g].get("role") in ("tool_default", "unattributed")]
    return {"lars_version": "0.1", "conforms": all(r["pass"] for r in res), "checks": res,
            "advisory": {"parameters_without_accountable_setter": accountable,
                         "note": "LARS v0.1 conformance requires a provenance entry per parameter; it does not by itself "
                                 "require that an accountable party (not a tool default) chose it."}}


def _setter(rep, name):
    for p in rep.get("parameters", []):
        if p.get("name") == name:
            return bool(p.get("set_by"))
    return False


def to_text(result: dict) -> str:
    L = [f"LARS v{result['lars_version']} conformance: {'CONFORMS' if result['conforms'] else 'DOES NOT CONFORM'}"]
    for c in result["checks"]:
        tag = "UNVERIFIABLE" if c.get("status") == "unverifiable" else ("PASS" if c["pass"] else "FAIL")
        L.append(f"  [{tag}] {c['check']:>2} {c['requirement']:<4} {c['name']}"
                 + (f"  -- {c['detail']}" if c["detail"] and (not c["pass"] or tag == "UNVERIFIABLE") else ""))
    a = result["advisory"]["parameters_without_accountable_setter"]
    if a:
        L.append(f"  advisory: no accountable setter for {a}")
    return "\n".join(L)
