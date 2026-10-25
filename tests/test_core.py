"""Core analysis: classification, LL144 handling, edge cases, schema and conformance."""
import json
from pathlib import Path

import jsonschema
import pytest

from libra_check.conform import check
from libra_check.core import ABOVE, BELOW, INDET, NE, InputError, analyze
from libra_check.render import to_html, to_markdown

from conftest import META, unit

SCHEMA = json.loads((Path(__file__).parents[1] / "src/libra_check/schema/libra-audit-report-0.1.schema.json").read_text())


def run(units, prov=None, **cli):
    if "thresholds" not in cli:
        cli["thresholds"] = None
    return analyze(units, META, cli=cli, declared=prov or {}, compute_power=cli.pop("power", False))


def ratio(rep, cat, u=0):
    return next(r for r in rep["units"][u]["ratios"] if r["category"] == cat)


def test_three_states():
    rep = run(unit(("A", 1000, 500), ("B", 1000, 250), ("C", 1000, 480), ("D", 60, 25)))
    assert rep["units"][0]["comparator_category"] == "A"
    assert ratio(rep, "B")["state_by_threshold"]["0.8"] == BELOW
    assert ratio(rep, "C")["state_by_threshold"]["0.8"] == ABOVE
    assert ratio(rep, "D")["state_by_threshold"]["0.8"] == INDET
    assert ratio(rep, "B")["point"] == pytest.approx(0.5)


def test_dcwp_published_example_reproduced():
    """6 RCNY §5-301 example tables (DCWP NOA, 2023): recomputed IRs match DCWP's printed values."""
    sex = [("Male", 1390, 667, 1.00), ("Female", 1181, 555, 0.979)]
    race = [("Hispanic or Latino", 408, 204, 0.97), ("White", 797, 412, 1.00), ("Black", 390, 170, 0.84),
            ("NHPI", 119, 52, 0.85), ("Asian", 616, 302, 0.95), ("AIAN", 41, 18, 0.85), ("Two+", 213, 96, 0.87)]
    inter = [("Hisp M", 205, 90, 0.841), ("Hisp F", 190, 82, 0.827), ("White M", 412, 215, 1.000),
             ("Black M", 226, 95, 0.806), ("NHPI M", 87, 37, 0.815), ("Asian M", 321, 167, 0.997),
             ("AIAN M", 24, 11, 0.878), ("Two+ M", 115, 52, 0.866), ("White F", 385, 197, 0.981),
             ("Black F", 164, 75, 0.876), ("NHPI F", 32, 15, 0.898), ("Asian F", 295, 135, 0.877),
             ("AIAN F", 17, 7, 0.789), ("Two+ F", 98, 44, 0.860)]
    units = [{"dimension": d, "categories": [{"label": a, "n": n, "k": k} for a, n, k, _ in t]}
             for d, t in (("sex", sex), ("race", race), ("intersectional", inter))]
    units[0]["categories"].append({"label": "Unknown", "n": 250, "k": 120})
    rep = run(units)
    for ui, (tab, nd) in enumerate(((sex, 3), (race, 2), (inter, 2))):
        u = rep["units"][ui]
        for a, n, k, ir in tab:
            if a == u["comparator_category"]:
                assert ir == 1.0
                continue
            # DCWP's race table divides rounded percentages; agree to 2 dp (allow 1 unit of rounding)
            assert abs(ratio(rep, a, ui)["point"] - ir) <= (0.0015 if nd == 3 else 0.011), a
    assert rep["units"][0]["unknown_n"] == 250
    # intersectional: AIAN F 0.789 point-below-0.80 but n=17 -> indeterminate, not a determinate finding
    r = ratio(rep, "AIAN F", 2)
    assert r["point_label_by_threshold"]["0.8"] == "point_below" and r["state_by_threshold"]["0.8"] == INDET


def test_unknown_never_comparator_or_focal():
    rep = run(unit(("A", 100, 40), ("B", 100, 30), ("Unknown", 50, 49)))
    u = rep["units"][0]
    assert u["comparator_category"] == "A"
    assert all(r["category"] != "Unknown" for r in u["ratios"])
    assert u["unknown_n"] == 50 and u["total_known_n"] == 200


def test_unknown_flag_column_and_missing_k():
    rep = run([{"dimension": "x", "categories": [{"label": "A", "n": 10, "k": 5}, {"label": "B", "n": 10, "k": 4},
                                                 {"label": "not provided", "n": 7, "unknown": "true"}]}])
    assert rep["units"][0]["unknown_n"] == 7


def test_two_percent_exclusion():
    cats = (("A", 5000, 2000), ("B", 4900, 1900), ("Tiny", 150, 140))   # Tiny = 1.5% of known, highest rate
    rep_no = run(unit(*cats))
    assert rep_no["units"][0]["comparator_category"] == "Tiny"
    rep = run(unit(*cats), small_category_exclusion=0.02)
    u = rep["units"][0]
    tiny = next(c for c in u["categories"] if c["label"] == "Tiny")
    assert tiny["excluded"] and "2%" in tiny["exclusion_reason"] and tiny["n"] == 150 and tiny["k"] == 140
    assert u["comparator_category"] == "A"
    assert any(w["code"] == "EXCLUDED_CATEGORIES" for w in rep["warnings"])


def test_zero_comparator_not_estimable():
    rep = run(unit(("A", 50, 0), ("B", 40, 0)))
    r = rep["units"][0]["ratios"][0]
    assert r["state_by_threshold"]["0.8"] == NE and r["point"] is None
    assert any(w["code"] == "ZERO_COMPARATOR" for w in rep["warnings"])


def test_focal_zero_and_all_selected():
    rep = run(unit(("A", 200, 200), ("B", 200, 0), ("C", 200, 199)))
    assert ratio(rep, "B")["state_by_threshold"]["0.8"] == BELOW
    assert ratio(rep, "B")["lower"] == 0.0
    assert ratio(rep, "C")["state_by_threshold"]["0.8"] == ABOVE


def test_tiny_groups_indeterminate():
    rep = run(unit(("A", 5, 3), ("B", 4, 1)))
    assert ratio(rep, "B")["state_by_threshold"]["0.8"] == INDET
    assert any(w["code"] == "SMALL_N" for w in rep["warnings"])


def test_tied_comparator_warning():
    rep = run(unit(("A", 100, 50), ("B", 200, 100), ("C", 100, 30)))
    assert rep["units"][0]["comparator_category"] == "B"   # largest n among tied, independent of order
    rep2 = run(unit(("B", 200, 100), ("A", 100, 50), ("C", 100, 30)))
    assert ratio(rep, "C")["state_by_threshold"] == ratio(rep2, "C")["state_by_threshold"]
    assert any(w["code"] == "TIED_COMPARATOR" for w in rep["warnings"])


def test_fixed_comparator():
    rep = run(unit(("A", 100, 50), ("B", 100, 60)), comparator_rule="fixed:A")
    assert rep["units"][0]["comparator_category"] == "A" and not rep["units"][0]["comparator_data_selected"]
    assert ratio(rep, "B")["point"] == pytest.approx(1.2)
    assert "projection" not in ratio(rep, "B")
    with pytest.raises(InputError):
        run(unit(("A", 100, 50), ("B", 100, 60)), comparator_rule="fixed:Z")


def test_projection_for_data_selected_max():
    rep = run(unit(("A", 300, 150), ("B", 300, 140), ("C", 300, 100)))
    u = rep["units"][0]
    assert u["comparator_projection"]["upper"] == 1.0
    for r in u["ratios"]:
        assert r["projection"]["lower"] <= r["lower"] + 1e-9   # simultaneous + data-selected: never narrower below


def test_min_n_not_estimable():
    rep = run(unit(("A", 500, 250), ("B", 20, 5)), min_n=30)
    r = ratio(rep, "B")
    assert r["state_by_threshold"]["0.8"] == NE and "min_n" in r["not_estimable_reason"]
    assert r["point"] is not None   # still disclosed


@pytest.mark.parametrize("burden,expect", [("report_only", INDET), ("deployer", "indeterminate_burden_on_deployer"),
                                            ("challenger", "indeterminate_burden_on_challenger")])
def test_burden_rule_decisions(burden, expect):
    rep = run(unit(("A", 100, 50), ("B", 100, 40)), burden_rule=burden)
    assert ratio(rep, "B")["decision_by_threshold"]["0.8"] == expect


def test_bonferroni_drives_decision_when_declared():
    cats = [("A", 2000, 1000)] + [(f"G{i}", 400, 140) for i in range(12)]
    rep = run(unit(*cats), multiplicity="bonferroni", comparator_rule="fixed:A")
    r = ratio(rep, "G0")
    assert r["state_by_threshold"]["0.8"] == BELOW
    assert r["adjusted_states"]["state_by_threshold"]["0.8"] == INDET
    assert r["decision_by_threshold"]["0.8"] == INDET
    assert rep["comparisons_count"] == 12


def test_multiple_thresholds():
    rep = run(unit(("A", 1000, 500), ("B", 1000, 400)), thresholds=[0.8, 0.85, 0.9])
    assert set(ratio(rep, "B")["state_by_threshold"]) == {"0.8", "0.85", "0.9"}
    assert ratio(rep, "B")["state_by_threshold"]["0.9"] == BELOW


def test_rate_reconstruction_and_envelope():
    units = [{"dimension": "r", "categories": [{"label": "A", "n": 900, "rate": "0.52"},
                                               {"label": "B", "n": 880, "rate": "0.43"}]}]
    rep = run(units)
    a = next(c for c in rep["units"][0]["categories"] if c["label"] == "A")
    assert a["k_reconstructed"] and a["k"] == 468 and a["k_bounds"] == [464, 472]
    r = ratio(rep, "B")
    assert r["rounding_envelope"]["lower"] <= r["lower"] and r["rounding_envelope"]["upper"] >= r["upper"]
    assert any(w["code"] == "RECONSTRUCTED_COUNTS" for w in rep["warnings"])


def test_fractional_k_is_reconstructed():
    rep = run([{"dimension": "s", "categories": [{"label": "F", "n": 573856, "k": 271433.888},
                                                 {"label": "M", "n": 478161, "k": 222823.026}]}])
    f = next(c for c in rep["units"][0]["categories"] if c["label"] == "F")
    assert f["k"] == 271434 and f["k_reconstructed"]


@pytest.mark.parametrize("cats", [
    [{"label": "A", "n": 10, "k": 11}], [{"label": "A", "n": -1, "k": 0}], [{"label": "A", "n": 10, "k": 5, "k_bounds": [6, 8]}],
    [{"label": "A", "n": 10.5, "k": 1}], [{"label": "A", "n": 10, "k": 1}, {"label": "A", "n": 5, "k": 1}],
    [{"label": "A", "n": 10, "rate": 1.2}]])
def test_bad_input(cats):
    with pytest.raises(InputError):
        run([{"dimension": "x", "categories": cats}])


def test_report_validates_and_is_deterministic(full_prov):
    u = unit(("A", 1000, 500), ("B", 1000, 420), ("C", 40, 12), ("Unknown", 30, 3))
    r1 = analyze(u, META, declared=full_prov, compute_power=True)
    r2 = analyze(u, META, declared=full_prov, compute_power=True)
    jsonschema.validate(r1, SCHEMA)
    assert r1["report_id"] == r2["report_id"]
    res = check(r1)
    assert res["conforms"], [c for c in res["checks"] if not c["pass"]]
    assert res["advisory"]["parameters_without_accountable_setter"] == []


def test_conformance_fails_when_undeclared():
    rep = run(unit(("A", 100, 50), ("B", 100, 40)))
    res = check(rep)
    assert not res["conforms"]
    assert not next(c for c in res["checks"] if c["requirement"] == "R2")["pass"]


def test_conformance_catches_pass_wording(full_prov):
    rep = analyze(unit(("A", 100, 50), ("B", 100, 40)), META, declared=full_prov, compute_power=False)
    r = next(r for r in rep["units"][0]["ratios"] if r["state_by_threshold"]["0.8"] == "indeterminate")
    r["decision_by_threshold"]["0.8"] = "pass"
    assert not next(c for c in check(rep)["checks"] if c["requirement"] == "R9")["pass"]


def test_conformance_catches_unknown_as_comparator(full_prov):
    rep = analyze(unit(("A", 100, 50), ("B", 100, 40), ("Unknown", 10, 9)), META, declared=full_prov, compute_power=False)
    rep["units"][0]["comparator_category"] = "Unknown"
    assert not next(c for c in check(rep)["checks"] if c["requirement"] == "R4")["pass"]


def test_power_and_hint(full_prov):
    rep = analyze(unit(("A", 400, 200), ("B", 300, 125)), META, declared=full_prov, compute_power=True)
    r = ratio(rep, "B")
    assert r["state_by_threshold"]["0.8"] == INDET
    assert r["additional_n_hint"]["scale_factor"] > 1
    band = r["precision"]
    assert band["flags_below_if_true_ir_at_most"] < 0.8 < band["certifies_at_or_above_if_true_ir_at_least"]
    assert band["method"] == "exact_enumeration"


def test_renderers(full_prov):
    rep = analyze(unit(("A", 1000, 500), ("B", 1000, 420), ("<script>", 50, 20)), META, declared=full_prov)
    md = to_markdown(rep)
    assert "INDETERMINATE" in md or "AT/ABOVE" in md
    assert "neither a pass" in md
    h = to_html(rep)
    assert "<script>" not in h and "&lt;script&gt;" in h


def test_test_data_flagged(full_prov):
    rep = analyze(unit(("A", 10, 5), ("B", 10, 4)), {**META, "data_source": "test"}, declared=full_prov, compute_power=False)
    assert any(w["code"] == "TEST_OR_SYNTHETIC_DATA" for w in rep["warnings"])


def test_missing_k_is_reported_and_excluded():
    rep = run([{"dimension": "x", "categories": [{"label": "A", "n": 100, "k": 50}, {"label": "B", "n": 100, "k": 40},
                                                 {"label": "C", "n": 3}]}])
    u = rep["units"][0]
    c = next(c for c in u["categories"] if c["label"] == "C")
    assert c["excluded"] and c["k"] is None and u["total_known_n"] == 203
    assert any(w["code"] == "MISSING_K" for w in rep["warnings"])
    assert not next(x for x in check(rep)["checks"] if x["requirement"] == "R1")["pass"]


def test_declared_k_bounds():
    rep = run([{"dimension": "x", "categories": [{"label": "A", "n": 100, "k": 50, "k_bounds": [49, 51]},
                                                 {"label": "B", "n": 100, "k": 40}]}])
    assert "rounding_envelope" in ratio(rep, "B")
