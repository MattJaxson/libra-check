"""Regression tests for the fixes made after an internal adversarial (red-team) review of version 0.1."""
import csv
import json

import numpy as np
import pytest

from libra_check.cli import main
from libra_check.conform import check
from libra_check.core import ABOVE, BELOW, INDET, NE, analyze
from libra_check.power import indeterminacy_band
from libra_check.intervals import z_for

from conftest import META, unit

COMPAS = [("African-American", 3696, 1795), ("Asian", 32, 23), ("Caucasian", 2454, 1488),
          ("Hispanic", 637, 405), ("Native American", 18, 8)]


def states(rep, t="0.8"):
    return {r["category"]: r["state_by_threshold"][t] for u in rep["units"] for r in u["ratios"]}


def test_attack1_pairwise_min_controls_false_flags_with_many_groups():
    """14 groups at parity, data-selected max comparator: per-claim false 'below' must stay <= alpha/2."""
    rng = np.random.default_rng(7)
    G, n, p, reps = 14, 60, 0.3, 150
    false_flags = claims = 0
    for _ in range(reps):
        k = rng.binomial(n, p, G)
        rep = analyze(unit(*[(f"g{i}", n, int(k[i])) for i in range(G)]), META, cli={"thresholds": [0.8]},
                      compute_power=False)
        s = list(states(rep).values())
        false_flags += sum(x == BELOW for x in s); claims += len(s)
    assert false_flags / claims <= 0.05


def test_attack1_comparator_gets_a_state():
    rep = analyze(unit(("small", 10, 6), ("big", 2000, 1000)), META, cli={}, compute_power=False)
    r = next(r for r in rep["units"][0]["ratios"] if r["is_comparator"])
    assert r["category"] == "small" and r["point"] == 1.0
    assert r["state_by_threshold"]["0.8"] == INDET          # not silently 'cleared'


def test_attack2_min_n_does_not_blank_the_audit():
    rep = analyze(unit(*COMPAS), META, cli={"min_n": 33, "thresholds": [0.85]}, compute_power=False)
    s = states(rep, "0.85")
    assert s["African-American"] == BELOW and s["Asian"] == NE
    assert any(w["code"] == "MIN_N_CHANGES_COMPARATOR" for w in rep["warnings"])


def test_attack8_tie_break_independent_of_order():
    a = analyze(unit(("A", 40, 20), ("B", 4000, 2000), ("C", 500, 180)), META, cli={}, compute_power=False)
    b = analyze(unit(("B", 4000, 2000), ("A", 40, 20), ("C", 500, 180)), META, cli={}, compute_power=False)
    assert states(a) == states(b)
    for sel in ("none",):
        a = analyze(unit(("A", 40, 20), ("B", 4000, 2000), ("C", 500, 180)), META, cli={"selection_adjustment": sel}, compute_power=False)
        b = analyze(unit(("B", 4000, 2000), ("A", 40, 20), ("C", 500, 180)), META, cli={"selection_adjustment": sel}, compute_power=False)
        assert states(a) == states(b)


def test_attack3_katz_flagged():
    rep = analyze(unit(("A", 100, 50), ("B", 100, 40)), META, cli={"interval_method": "katz_log"}, compute_power=False)
    assert any(w["code"] == "ANTICONSERVATIVE_METHOD" for w in rep["warnings"])


def test_attack10_low_decimals_widen_envelope():
    rep = analyze([{"dimension": "x", "categories": [{"label": "A", "n": 200, "rate": "0.5"},
                                                     {"label": "B", "n": 200, "rate": "0.3"}]}], META, cli={}, compute_power=False)
    b = next(c for c in rep["units"][0]["categories"] if c["label"] == "B")
    assert b["k_bounds"] == [50, 70]   # boundary included (conservative)
    assert any(w["code"] == "DECIMALS_INFERRED_LOW" for w in rep["warnings"])
    rep2 = analyze([{"dimension": "x", "categories": [{"label": "A", "n": 200, "rate": "0.5", "rate_decimals": 2},
                                                      {"label": "B", "n": 200, "rate": "45%"}]}], META, cli={}, compute_power=False)
    b = next(c for c in rep2["units"][0]["categories"] if c["label"] == "B")
    assert b["k"] == 90 and b["k_bounds"] == [89, 91]


def test_attack11_band_continuous_across_switch():
    z = z_for(0.10)
    a = indeterminacy_band(1000, 20000, 0.02, 0.8, z)["flags_below_if_true_ir_at_most"]
    b = indeterminacy_band(1001, 20000, 0.02, 0.8, z)["flags_below_if_true_ir_at_most"]
    assert abs(a - b) <= 0.03


def test_attack6_check12_unverifiable_without_commitment(full_prov):
    rep = analyze(unit(("A", 100, 50), ("B", 100, 40)), META, declared=full_prov, compute_power=False)
    c12 = next(c for c in check(rep)["checks"] if c["check"] == 12)
    assert c12["status"] == "unverifiable"
    from libra_check.provenance import resolve
    from libra_check.core import params_sha256
    h = params_sha256(resolve({}, full_prov))
    rep2 = analyze(unit(("A", 100, 50), ("B", 100, 40)), META, declared=full_prov, compute_power=False, precommitted_hash=h)
    assert rep2["precommitment"]["matches"]
    assert next(c for c in check(rep2)["checks"] if c["check"] == 12)["status"] == "verified_against_commitment"
    rep3 = analyze(unit(("A", 100, 50), ("B", 100, 40)), META, declared=full_prov, compute_power=False, precommitted_hash="0" * 64)
    assert any(w["code"] == "PRECOMMITMENT_MISMATCH" for w in rep3["warnings"])


def test_attack7_burden_line_rendered():
    from libra_check.render import to_markdown
    rep = analyze(unit(("A", 100, 50), ("B", 100, 40)), META, cli={}, compute_power=False)
    assert "No burden rule assigned: indeterminate results are unresolved, not passes" in to_markdown(rep)
    assert "Not a legal finding" in to_markdown(rep)
    assert any(w["code"] == "NO_BURDEN_RULE_ASSIGNED" for w in rep["warnings"])


def test_attack5_pooled_and_estimand():
    rep = analyze(unit(("A", 100, 50), ("B", 100, 40)), {**META, "data_scope": "pooled:12"},
                  cli={"estimand": "finite_population"}, compute_power=False)
    codes = {w["code"] for w in rep["warnings"]}
    assert {"POOLED_DATA", "FINITE_POPULATION_ESTIMAND"} <= codes


def test_attack9_exclusion_base():
    cats = (("A", 4900, 2000), ("B", 4900, 1900), ("T", 200, 150), ("Unknown", 5000, 1000))
    r_known = analyze(unit(*cats), META, cli={"small_category_exclusion": 0.02}, compute_power=False)
    r_all = analyze(unit(*cats), META, cli={"small_category_exclusion": 0.02, "exclusion_base": "all_assessed"}, compute_power=False)
    ex = lambda r: next(c for c in r["units"][0]["categories"] if c["label"] == "T")["excluded"]  # noqa: E731
    assert ex(r_known) is False and ex(r_all) is True


def _write(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def test_attack4_cut_unstable_and_missing_scores(tmp_path):
    rng = np.random.default_rng(3)
    rows = []
    for i in range(1200):
        sex = "F" if i % 2 else "M"
        s = int(np.clip(rng.normal(3.0 if sex == "F" else 3.3, 1.0), 1, 5).round())
        rows.append({"sex": sex, "race": "W" if i % 3 else "B", "score": s if i % 97 else ""})
    p = tmp_path / "rubric.csv"; _write(p, rows)
    out = tmp_path / "r.json"
    assert main(["ll144", str(p), "--score-col", "score", "--no-power", "--no-intersectional", "--out", str(out)]) == 0
    rep = json.loads(out.read_text())
    codes = {w["code"] for w in rep["warnings"]}
    assert "CUT_UNSTABLE" in codes and "MISSING_SCORES" in codes and "INTERSECTIONAL_REQUIRED" in codes
    assert rep["cut_sensitivity"]["ties_at_median"] > 0


def test_attack12_aliases_and_row_errors(tmp_path):
    p = tmp_path / "c.csv"; p.write_text("Group,Applicants,Selected\nA,100,50\nB,100,40\n")
    out = tmp_path / "r.json"
    assert main(["analyze", str(p), "--no-power", "--out", str(out)]) == 0
    p.write_text("Group,Applicants,Selected\nA,100,50\nB,abc,40\n")
    assert main(["analyze", str(p), "--no-power", "--out", str(out)]) == 2


def test_sensitivity_command(capsys):
    from libra_check.sensitivity import grid
    res = grid(unit(*COMPAS), META)
    aa = next(c for c in res["categories"] if c["category"] == "African-American")
    assert not aa["verdict_stable_within_each_threshold"]


def test_validation_bug1_katz_zero_focal_never_certified():
    rep = analyze([{"dimension": "d", "categories": [{"label": "ref", "n": 1000, "k": 1}, {"label": "foc", "n": 20, "k": 0}]}],
                  META, cli={"interval_method": "katz_log", "selection_adjustment": "none"}, compute_power=False)
    r = next(r for r in rep["units"][0]["ratios"] if r["category"] == "foc")
    assert r["lower"] == 0.0 and r["state_by_threshold"]["0.8"] != ABOVE
