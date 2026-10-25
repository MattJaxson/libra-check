# Impact-ratio report — ProPublica COMPAS Broward County data

Report `lc-de15cbd077bd0131` · generated 2026-10-13T05:23:03+00:00 · libra-check 0.2.0 · LARS v0.1

| | |
|---|---|
| Deployer | — |
| Auditor | — |
| Decision point | COMPAS two-year recidivism label (favourable = no recidivism) |
| Outcome definition (what counts as k) | no new charge within two years (two_year_recid = 0) |
| Rate type | rate |
| Data source / window | historical / as in preprint v1.1 source file |
| Comparator rule | fixed:Caucasian |
| Threshold(s) θ | 0.8, 0.85 |
| Interval | two-sided 95% (0.025 error per bound), mover_wilson |
| Minimum n | 30 |
| Burden rule for indeterminate results | **No burden rule assigned: indeterminate results are unresolved, not passes.** |
| Comparator selection accounted for | none |
| Estimand / data scope | process / own |

> **Not a legal finding.** This report describes statistical evidence relative to declared parameters. NYC Local Law 144 and its rules set no impact-ratio threshold.

## How to read this

Each impact ratio (IR) is a category's rate divided by the comparator's rate, shown with a 95% interval. **Determinate below**: the whole interval is under θ. **Determinate at/above**: the whole interval is at or over θ. **Indeterminate**: the data are consistent with values on both sides of θ — this is *neither a pass nor a fail*; what follows from it is set by the declared burden rule. **Not estimable**: the ratio cannot be computed (zero comparator rate, or n under the declared minimum).

## Summary

| θ | below | indeterminate | at/above | not estimable | familywise below | point estimate below θ |
|---|---|---|---|---|---|---|
| 0.8 | 0 | 1 | 2 | 1 | 0 | 1 |
| 0.85 | 1 | 0 | 2 | 1 | 1 | 2 |

3 comparisons in 1 unit(s). Familywise column: Bonferroni over all comparisons.

## Unit: race

Comparator: **Caucasian** (rate 0.6064) — fixed in advance. Known individuals: 6837; unknown category: 0 (reported, not in ratios).

| Category | n | k | rate | share of known | status |
|---|---|---|---|---|---|
| African-American | 3696 | 1795 | 0.4857 | 0.541 | included |
| Asian | 32 | 23 | 0.7188 | 0.005 | included |
| Caucasian | 2454 | 1488 | 0.6064 | 0.359 | included |
| Hispanic | 637 | 405 | 0.6358 | 0.093 | included |
| Native American | 18 | 8 | 0.4444 | 0.003 | included |

| Category | IR | interval | state @ 0.8 | state @ 0.85 | point-only reading @ 0.8 | ignoring comparator selection @ 0.8 | resolvable band (80% power) |
|---|---|---|---|---|---|---|---|
| African-American | 0.801 | [0.765, 0.839] | INDETERMINATE | BELOW θ (determinate) | point_at_or_above | — | below if ≤0.740; at/above if ≥0.860 |
| Asian | 1.185 | [0.899, 1.397] | AT/ABOVE θ (determinate) | AT/ABOVE θ (determinate) | point_at_or_above | — | below if ≤0.405; at/above if ≥1.200 |
| Hispanic | 1.049 | [0.979, 1.119] | AT/ABOVE θ (determinate) | AT/ABOVE θ (determinate) | point_at_or_above | — | below if ≤0.700; at/above if ≥0.900 |
| Native American | 0.733 | [0.405, 1.095] | NOT ESTIMABLE | NOT ESTIMABLE | point_below | — | — |

Precision statements (not predictions): if both point rates held, the interval would exclude θ=0.8 at about:
- African-American: 1510.27× the current sample (focal n ≈ 5581953, comparator n ≈ 3706200)

## Parameter provenance (who chose each rule)

| Parameter | Value | Set by | Role | Process | Source |
|---|---|---|---|---|---|
| thresholds | [0.8, 0.85] | Matt Jackson (worked example) | researcher | illustration; 0.80 echoes the four-fifths rule of thumb, 0.85 shows sensitivity | unassigned by rule (illustration only) |
| alpha | 0.05 | Matt Jackson (worked example) | researcher | two-sided 95% to match the preprint's 95% intervals and LARS v0.1 R6 SHOULD-default | unassigned by rule; LARS v0.1 R6 default |
| interval_method | mover_wilson | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| comparator_rule | fixed:Caucasian | Matt Jackson (worked example) | researcher | same reference group as preprint v1.1 | Jackson (2026) preprint v1.1, doi:10.5281/zenodo.23328063 |
| small_category_exclusion | None | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| unknown_category_handling | exclude_and_report | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| min_n | 30 | Matt Jackson (worked example) | researcher | same reportable-n rule as preprint v1.1 | Jackson (2026) preprint v1.1 (minimum_group_n_for_aggregate_counts = 30) |
| burden_rule | report_only | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| multiplicity | none | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| outcome_definition | no new charge within two years (two_year_recid = 0) | Matt Jackson (worked example) | researcher | same outcome as preprint v1.1 | Jackson (2026) preprint v1.1 |
| category_scheme | as supplied in input | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| data_window | as in preprint v1.1 source file | Matt Jackson (worked example) | researcher | public dataset | preprint v1.1 data acquisition notes |
| selection_rule | rate | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| score_cut | None | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| selection_adjustment | pairwise_min | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| exclusion_base | known | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |
| estimand | process | libra-check | tool_default | libra-check default; not chosen by any accountable party | unassigned by rule |

## Warnings

- `SMALL_N` unit race, Native American: n=18 < 30
- `TOOL_DEFAULT_PARAMETERS` set by libra-check default, not by an accountable party: ['interval_method', 'small_category_exclusion', 'unknown_category_handling', 'burden_rule', 'multiplicity', 'category_scheme', 'selection_rule', 'score_cut', 'selection_adjustment', 'exclusion_base', 'estimand']
- `NO_BURDEN_RULE_ASSIGNED` no accountable party assigned a burden rule: indeterminate results are unresolved, not passes

## Reproducibility

Software libra-check 0.2.0 (commit b4eaa793ec60bcaca0145f1e2183ced6cfa4b195); input sha256 `c2b9a884f3651304…`; parameters sha256 `d99aaff8a872f005…`. Interval method: MOVER-R with Wilson limits: Donner & Zou (2012) Stat Methods Med Res 21(4):347-359, doi:10.1177/0962280210383082; Newcombe (2016) Stat Methods Med Res 25(5):1774-1778, doi:10.1177/0962280213502144; Wilson (1927) JASA 22:209-212, doi:10.1080/01621459.1927.10502953. Zero handling: closed form; Wilson limits are defined at k=0 and k=n; focal k=0 gives lower=0; comparator k=0 makes the ratio not estimable.

*This report describes statistical evidence relative to declared parameters. It makes no legal determination.*
