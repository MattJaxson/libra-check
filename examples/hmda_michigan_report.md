# Impact-ratio report — HMDA Michigan single-lender filing

Report `lc-d5e58d9afc343975` · generated 2026-10-13T05:22:38+00:00 · libra-check 0.2.0 · LARS v0.1

| | |
|---|---|
| Deployer | — |
| Auditor | — |
| Decision point | HMDA action_taken (origination) |
| Outcome definition (what counts as k) | loan originated (HMDA action_taken = 1) |
| Rate type | rate |
| Data source / window | historical / as in preprint v1.1 source file |
| Comparator rule | fixed:White |
| Threshold(s) θ | 0.8, 0.85 |
| Interval | two-sided 90% (0.05 error per bound), mover_wilson |
| Minimum n | 30 |
| Burden rule for indeterminate results | **No burden rule assigned: indeterminate results are unresolved, not passes.** |
| Comparator selection accounted for | none |
| Estimand / data scope | process / own |

> **Not a legal finding.** This report describes statistical evidence relative to declared parameters. NYC Local Law 144 and its rules set no impact-ratio threshold.

## How to read this

Each impact ratio (IR) is a category's rate divided by the comparator's rate, shown with a 90% interval. **Determinate below**: the whole interval is under θ. **Determinate at/above**: the whole interval is at or over θ. **Indeterminate**: the data are consistent with values on both sides of θ — this is *neither a pass nor a fail*; what follows from it is set by the declared burden rule. **Not estimable**: the ratio cannot be computed (zero comparator rate, or n under the declared minimum).

## Summary

| θ | below | indeterminate | at/above | not estimable | familywise below | point estimate below θ |
|---|---|---|---|---|---|---|
| 0.8 | 0 | 2 | 0 | 2 | 0 | 3 |
| 0.85 | 0 | 2 | 0 | 2 | 0 | 4 |

2 comparisons in 1 unit(s). Familywise column: Bonferroni over all comparisons.

## Unit: race

Comparator: **White** (rate 0.4200) — fixed in advance. Known individuals: 3831; unknown category: 0 (reported, not in ratios).

| Category | n | k | rate | share of known | status |
|---|---|---|---|---|---|
| American Indian or Alaska Native | 29 | 4 | 0.1379 | 0.008 | included |
| Asian | 232 | 75 | 0.3233 | 0.061 | included |
| Black or African American | 632 | 217 | 0.3434 | 0.165 | included |
| Native Hawaiian or Other Pacific Islander | 5 | 1 | 0.2000 | 0.001 | included |
| White | 2933 | 1232 | 0.4200 | 0.766 | included |

| Category | IR | interval | state @ 0.8 | state @ 0.85 | point-only reading @ 0.8 | ignoring comparator selection @ 0.8 | resolvable band (80% power) |
|---|---|---|---|---|---|---|---|
| American Indian or Alaska Native | 0.328 | [0.151, 0.654] | NOT ESTIMABLE | NOT ESTIMABLE | point_below | — | — |
| Asian | 0.770 | [0.652, 0.898] | INDETERMINATE | INDETERMINATE | point_below | — | below if ≤0.615; at/above if ≥0.995 |
| Black or African American | 0.817 | [0.740, 0.899] | INDETERMINATE | INDETERMINATE | point_at_or_above | — | below if ≤0.680; at/above if ≥0.925 |
| Native Hawaiian or Other Pacific Islander | 0.476 | [0.109, 1.346] | NOT ESTIMABLE | NOT ESTIMABLE | point_below | — | — |

Precision statements (not predictions): if both point rates held, the interval would exclude θ=0.8 at about:
- Asian: 16.848× the current sample (focal n ≈ 3909, comparator n ≈ 49415)
- Black or African American: 20.55× the current sample (focal n ≈ 12988, comparator n ≈ 60272)

## Parameter provenance (who chose each rule)

| Parameter | Value | Set by | Role | Process | Source |
|---|---|---|---|---|---|
| thresholds | [0.8, 0.85] | Matt Jackson (worked example) | researcher | illustration; 0.80 echoes the four-fifths rule of thumb, 0.85 shows sensitivity | unassigned by rule (illustration only) |
| alpha | 0.1 | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| interval_method | mover_wilson | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| comparator_rule | fixed:White | Matt Jackson (worked example) | researcher | same reference group as preprint v1.1 | Jackson (2026) preprint v1.1, doi:10.5281/zenodo.23328063 |
| small_category_exclusion | None | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| unknown_category_handling | exclude_and_report | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| min_n | 30 | Matt Jackson (worked example) | researcher | same reportable-n rule as preprint v1.1 | Jackson (2026) preprint v1.1 (minimum_group_n_for_aggregate_counts = 30) |
| burden_rule | report_only | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| multiplicity | none | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| outcome_definition | loan originated (HMDA action_taken = 1) | Matt Jackson (worked example) | researcher | same outcome as preprint v1.1 | Jackson (2026) preprint v1.1 |
| category_scheme | as supplied in input | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| data_window | as in preprint v1.1 source file | Matt Jackson (worked example) | researcher | public dataset | preprint v1.1 data acquisition notes |
| selection_rule | rate | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| score_cut | None | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| selection_adjustment | pairwise_min | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| exclusion_base | known | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| estimand | process | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |

## Warnings

- `SMALL_N` unit race, American Indian or Alaska Native: n=29 < 30
- `SMALL_N` unit race, Native Hawaiian or Other Pacific Islander: n=5 < 30
- `TOOL_DEFAULT_PARAMETERS` set by libra-check default, not by an accountable party: ['alpha', 'interval_method', 'small_category_exclusion', 'unknown_category_handling', 'burden_rule', 'multiplicity', 'category_scheme', 'selection_rule', 'score_cut', 'selection_adjustment', 'exclusion_base', 'estimand']
- `NO_BURDEN_RULE_ASSIGNED` no accountable party assigned a burden rule: indeterminate results are unresolved, not passes

## Reproducibility

Software libra-check 0.2.0 (commit b4eaa793ec60bcaca0145f1e2183ced6cfa4b195); input sha256 `9e798fd83ef4de9e…`; parameters sha256 `e5d983b20ee34187…`. Interval method: MOVER-R with Wilson limits: Donner & Zou (2012) Stat Methods Med Res 21(4):347-359, doi:10.1177/0962280210383082; Newcombe (2016) Stat Methods Med Res 25(5):1774-1778, doi:10.1177/0962280213502144; Wilson (1927) JASA 22:209-212, doi:10.1080/01621459.1927.10502953. Zero handling: closed form; Wilson limits are defined at k=0 and k=n; focal k=0 gives lower=0; comparator k=0 makes the ratio not estimable.

*This report describes statistical evidence relative to declared parameters. It makes no legal determination.*
