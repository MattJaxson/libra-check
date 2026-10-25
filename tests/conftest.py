import pytest

FULL_PROV = {
    name: {"value": val, "set_by": "Test Body", "role": "regulator", "process": "unit test", "date": "2026-10-13",
           "source": "test fixture"}
    for name, val in {
        "thresholds": [0.8], "alpha": 0.10, "interval_method": "mover_wilson", "comparator_rule": "max_rate_eligible",
        "small_category_exclusion": None, "unknown_category_handling": "exclude_and_report", "min_n": None,
        "burden_rule": "deployer", "multiplicity": "none", "outcome_definition": "advanced to interview",
        "category_scheme": "EEO-1", "data_window": "2025-01-01/2025-12-31", "selection_rule": "rate", "score_cut": None,
        "selection_adjustment": "pairwise_min", "exclusion_base": "known", "estimand": "process",
    }.items()
}
META = {"system": "Test AEDT", "decision_point": "resume screen", "data_source": "historical"}


@pytest.fixture
def full_prov():
    import copy
    return copy.deepcopy(FULL_PROV)


def unit(*cats, dim="race"):
    return [{"dimension": dim, "categories": [dict(zip(("label", "n", "k"), c)) for c in cats]}]
