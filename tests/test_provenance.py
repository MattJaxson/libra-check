import json

import pytest

from libra_check.core import analyze
from libra_check.provenance import ProvenanceError, load_provenance, resolve

from conftest import META, unit


def test_defaults_are_recorded_as_tool_defaults():
    p = resolve({}, {})
    assert p["thresholds"].role == "tool_default" and p["thresholds"].value == [0.8]
    assert p["outcome_definition"].value == "UNDECLARED"


def test_cli_values_unattributed():
    p = resolve({"thresholds": [0.85]}, {})
    assert p["thresholds"].role == "unattributed" and p["thresholds"].value == [0.85]


def test_conflict_between_cli_and_declared(full_prov):
    with pytest.raises(ProvenanceError, match="conflicts"):
        resolve({"thresholds": [0.9]}, full_prov)
    resolve({"thresholds": [0.8]}, full_prov)  # agreeing value is fine


def test_strict_mode(full_prov):
    with pytest.raises(ProvenanceError):
        resolve({}, {}, strict=True)
    resolve({}, full_prov, strict=True)


def test_bad_role_and_values(full_prov):
    bad = dict(full_prov); bad["alpha"] = {**bad["alpha"], "role": "boss"}
    with pytest.raises(ProvenanceError, match="role"):
        resolve({}, bad)
    for k, v in (("alpha", 1.5), ("thresholds", [0]), ("burden_rule", "nobody"), ("comparator_rule", "min"),
                 ("interval_method", "wald")):
        b = dict(full_prov); b[k] = {**b[k], "value": v}
        with pytest.raises(ProvenanceError):
            resolve({}, b)


def test_ll144_preset_cites_rule():
    p = resolve({"small_category_exclusion": 0.02}, {}, preset="ll144")
    assert "6 RCNY §5-301(d)" in p["small_category_exclusion"].source
    assert p["comparator_rule"].role == "regulator" and "§5-300" in p["comparator_rule"].source
    assert "no threshold" in p["thresholds"].source


def test_load_list_and_dict_forms(tmp_path, full_prov):
    a = tmp_path / "a.json"; a.write_text(json.dumps({"parameters": [{"name": k, **v} for k, v in full_prov.items()]}))
    b = tmp_path / "b.json"; b.write_text(json.dumps(full_prov))
    assert load_provenance(a) == load_provenance(b)


def test_report_lists_every_parameter(full_prov):
    rep = analyze(unit(("A", 10, 5), ("B", 10, 4)), META, declared=full_prov, compute_power=False)
    names = {p["name"] for p in rep["parameters"]}
    assert {"thresholds", "alpha", "burden_rule", "min_n", "comparator_rule", "outcome_definition"} <= names
    assert all(p["set_by"] == "Test Body" for p in rep["parameters"])
