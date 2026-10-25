"""Parameter provenance record (LARS v0.1 §5, R13-R15).

Every governance parameter that can change a verdict is recorded with
name, value, set_by, role, process, date, source, changed_from.
A parameter that nobody declared is still recorded -- as a libra-check default, so the
report shows that no accountable party chose it.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROLES = ("community_body", "regulator", "auditor", "vendor", "employer_deployer",
         "researcher", "standard_default", "tool_default", "unattributed")

#: governance parameters (LARS v0.1 §2) -> libra-check default value
GOVERNANCE_DEFAULTS: dict[str, Any] = {
    "thresholds": [0.80],
    "alpha": 0.10,                       # two-sided; = 5% one-sided error per determinate claim
    "interval_method": "mover_wilson",
    "comparator_rule": "max_rate_eligible",
    "small_category_exclusion": None,    # share of known; None = no exclusion
    "unknown_category_handling": "exclude_and_report",
    "min_n": None,
    "burden_rule": "report_only",
    "multiplicity": "none",
    "outcome_definition": "UNDECLARED",
    "category_scheme": "as supplied in input",
    "data_window": "UNDECLARED",
    "selection_rule": "rate",
    "score_cut": None,
    "selection_adjustment": "pairwise_min",   # how the data-selected comparator is accounted for
    "exclusion_base": "known",                 # base of the small-category share: known | all_assessed
    "estimand": "process",                     # process | finite_population
}
REQUIRED_DECLARATIONS = ("outcome_definition", "data_window")

BURDEN_RULES = ("report_only", "deployer", "challenger")
COMPARATOR_RULES_FIXED_PREFIX = "fixed:"
COMPARATOR_RULES = ("max_rate_eligible", "max_rate_all")

DEFAULT_PROCESS = "libra-check default; not chosen by any accountable party"
UNASSIGNED = "unassigned by rule"

# Rule text verified 2026-10-13 at
# https://rules.cityofnewyork.us/wp-content/uploads/2023/04/DCWP-NOA-for-Use-of-Automated-Employment-Decisionmaking-Tools-2.pdf
LL144_PRESET: dict[str, dict] = {
    "comparator_rule": dict(value="max_rate_eligible", set_by="NYC DCWP", role="regulator", process="adopted rule",
                            source="6 RCNY §5-300 ('Impact ratio' = rate / rate of the most selected or highest-scoring category)"),
    "unknown_category_handling": dict(value="exclude_and_report", set_by="NYC DCWP", role="regulator", process="adopted rule",
                                      source="6 RCNY §5-301(b)(5), (c)(5); §5-303(a)(1)"),
    "score_cut": dict(value="median_full_sample", set_by="NYC DCWP", role="regulator", process="adopted rule",
                      source="6 RCNY §5-300 ('Scoring Rate'); §5-301(c)(1) ('median score for the full sample of applicants')"),
    "thresholds": dict(value=[0.80], set_by="libra-check", role="tool_default", process=DEFAULT_PROCESS,
                       source=UNASSIGNED + " (LL144 and 6 RCNY §5-300..5-304 set no threshold)"),
    "alpha": dict(value=0.10, set_by="libra-check", role="tool_default", process=DEFAULT_PROCESS,
                  source=UNASSIGNED + " (LL144 requires no uncertainty statement)"),
    "min_n": dict(value=None, set_by="libra-check", role="tool_default", process=DEFAULT_PROCESS,
                  source=UNASSIGNED),
    "burden_rule": dict(value="report_only", set_by="libra-check", role="tool_default", process=DEFAULT_PROCESS,
                        source=UNASSIGNED),
}
LL144_EXCLUSION_SOURCE = ("6 RCNY §5-301(d) (auditor MAY exclude a category < 2% of the data; justification, n and "
                          "rate of the excluded category must be reported)")


class ProvenanceError(ValueError):
    pass


@dataclass
class Param:
    name: str
    value: Any
    set_by: str
    role: str
    process: str
    date: str | None = None
    source: str | None = None
    changed_from: Any = None
    is_default: bool = False

    def as_dict(self) -> dict:
        d = dict(name=self.name, value=self.value, set_by=self.set_by, role=self.role, process=self.process,
                 date=self.date, source=self.source, is_default=self.is_default)
        if self.changed_from is not None:
            d["changed_from"] = self.changed_from
        return d


def _norm_value(name, v):
    if name == "thresholds":
        if isinstance(v, (int, float)):
            v = [v]
        return [float(x) for x in v]
    return v


def load_provenance(path: str | Path | None) -> dict[str, dict]:
    """Accepts {"parameters": [ {name,...}, ...]} or {name: {value,...}}."""
    if path is None:
        return {}
    raw = json.loads(Path(path).read_text())
    if isinstance(raw, dict) and "parameters" in raw:
        raw = raw["parameters"]
    if isinstance(raw, list):
        out = {}
        for e in raw:
            if "name" not in e:
                raise ProvenanceError(f"provenance entry without 'name': {e}")
            out[e["name"]] = {k: v for k, v in e.items() if k != "name"}
        return out
    if isinstance(raw, dict):
        return raw
    raise ProvenanceError("provenance file must be a JSON object or list")


def validate_entry(name: str, e: dict) -> None:
    if "value" not in e:
        raise ProvenanceError(f"provenance for '{name}' has no 'value'")
    if e.get("role") not in ROLES:
        raise ProvenanceError(f"provenance for '{name}': role must be one of {ROLES}, got {e.get('role')!r}")
    if not e.get("set_by"):
        raise ProvenanceError(f"provenance for '{name}' has no 'set_by'")


def resolve(cli: dict[str, Any], declared: dict[str, dict], preset: str | None = None,
            strict: bool = False) -> dict[str, Param]:
    """Merge preset < declared provenance file; CLI values must agree with declared values.

    cli: parameter values given on the command line / API (None = not given).
    strict: raise if any governance parameter ends up as a tool default or unattributed.
    """
    base: dict[str, dict] = {}
    if preset == "ll144":
        base.update(copy.deepcopy(LL144_PRESET))
    elif preset not in (None, "none"):
        raise ProvenanceError(f"unknown preset {preset!r}")
    for k, e in declared.items():
        validate_entry(k, e)
        base[k] = dict(e)
    params: dict[str, Param] = {}
    for name, default in GOVERNANCE_DEFAULTS.items():
        cv = cli.get(name)
        if name in base:
            e = base[name]
            val = _norm_value(name, e["value"])
            if cv is not None and _norm_value(name, cv) != val:
                raise ProvenanceError(
                    f"parameter '{name}': command-line value {cv!r} conflicts with declared value {val!r} "
                    f"(set by {e.get('set_by')}); change the provenance record instead (R15)")
            params[name] = Param(name, val, e["set_by"], e["role"], e.get("process", "not stated"),
                                 e.get("date"), e.get("source"), e.get("changed_from"),
                                 is_default=e["role"] == "tool_default")
        elif cv is not None:
            params[name] = Param(name, _norm_value(name, cv), "unattributed (command line / API caller)",
                                 "unattributed", "value supplied without a provenance record", None,
                                 UNASSIGNED + "; no setter declared")
        else:
            params[name] = Param(name, _norm_value(name, default), "libra-check", "tool_default",
                                 DEFAULT_PROCESS, None, UNASSIGNED, is_default=True)
    if preset == "ll144" and "small_category_exclusion" not in base \
            and params["small_category_exclusion"].value is not None:
        params["small_category_exclusion"].source = LL144_EXCLUSION_SOURCE + "; option exercised by unattributed caller"
    _check_values(params)
    if strict:
        bad = [p.name for p in params.values() if p.role in ("tool_default", "unattributed")]
        und = [n for n in REQUIRED_DECLARATIONS if params[n].value == "UNDECLARED"]
        if bad or und:
            raise ProvenanceError(f"--require-provenance: undeclared or unattributed parameters: {sorted(set(bad + und))}")
    return params


def _check_values(p: dict[str, Param]) -> None:
    th = p["thresholds"].value
    if not th or any(not (0 < t <= 1.5) for t in th):
        raise ProvenanceError(f"thresholds must be in (0, 1.5]: {th}")
    a = p["alpha"].value
    if not (0 < float(a) < 1):
        raise ProvenanceError(f"alpha must be in (0,1): {a}")
    from .intervals import METHODS
    if p["interval_method"].value not in METHODS:
        raise ProvenanceError(f"interval_method must be one of {sorted(METHODS)}")
    cr = p["comparator_rule"].value
    if cr not in COMPARATOR_RULES and not str(cr).startswith(COMPARATOR_RULES_FIXED_PREFIX):
        raise ProvenanceError(f"comparator_rule must be one of {COMPARATOR_RULES} or 'fixed:<category>'")
    ex = p["small_category_exclusion"].value
    if ex is not None and not (0 <= float(ex) < 0.5):
        raise ProvenanceError("small_category_exclusion must be a share in [0, 0.5) or null")
    if p["burden_rule"].value not in BURDEN_RULES:
        raise ProvenanceError(f"burden_rule must be one of {BURDEN_RULES}")
    if p["multiplicity"].value not in ("none", "bonferroni"):
        raise ProvenanceError("multiplicity must be 'none' or 'bonferroni'")
    mn = p["min_n"].value
    if mn is not None and int(mn) < 1:
        raise ProvenanceError("min_n must be a positive integer or null")
    if p["selection_adjustment"].value not in ("pairwise_min", "none"):
        raise ProvenanceError("selection_adjustment must be 'pairwise_min' or 'none'")
    if p["exclusion_base"].value not in ("known", "all_assessed"):
        raise ProvenanceError("exclusion_base must be 'known' or 'all_assessed'")
    if p["estimand"].value not in ("process", "finite_population"):
        raise ProvenanceError("estimand must be 'process' or 'finite_population'")
    if p["unknown_category_handling"].value != "exclude_and_report":
        raise ProvenanceError("only 'exclude_and_report' is implemented (LARS R4; 6 RCNY §5-301(b)(5))")
