# Libra Audit Reporting Standard (LARS) v0.1 (draft for comment)

**Status:** Draft v0.1 for public comment, published 2026-10-25. Author: Matthew Jackson, independent researcher, Detroit, Michigan. Not adopted or endorsed by any public body, regulator or standards organization. Comments: open an issue in this repository.
**Scope:** how to **disclose** group disparity metrics (selection-rate and scoring-rate impact ratios) for automated or AI-assisted decision systems, with sampling uncertainty and the provenance of every audit parameter.
**What it is not:** it does not set a legal threshold, does not define "fair", and does not say what any law requires. It is a disclosure format that a regulator, buyer or auditor can adopt by reference.
**Basis:** this spec rests on long-established statistics (interval estimation for a ratio of two binomial proportions; Morris & Lobsenz 2000, doi:10.1111/j.1744-6570.2000.tb00195.x) and on the author's earlier preprint, Libra v1.1 (Jackson 2026, doi:10.5281/zenodo.23328063). It is not a new statistical method. What it adds is a disclosure rule, the attribution of every verdict-changing parameter to a named party, and a declared consequence for uncertain results. **Overlap review pending:** the CDT et al. Civil Rights Standards for 21st Century Employment Selection Procedures (2022), IEEE 3198-2025 and ISO/IEC TS 12791:2024 cover nearby ground and have not yet been compared clause by clause with this draft. Pointers to overlaps are welcome.
**Machine-readable twin:** the JSON Schemas in `schemas/` define the record. The reference implementation, `libra-check` (Apache-2.0, separate repository), emits `libra-audit-report/0.1` records implementing this spec. If this text and the schemas disagree, the schema field names win and this text will be corrected.

Key words MUST, MUST NOT, SHOULD, MAY follow RFC 2119 (https://www.rfc-editor.org/rfc/rfc2119).

---

## 1. Why this exists (two problems)

1. **A point estimate can't settle a threshold question when samples are small.** An impact ratio of 0.82 from 40 applicants and the same ratio from 40,000 are reported identically today. The first is consistent with true ratios well below or above 0.80. The 1978 Uniform Guidelines already tie the four-fifths rule to sample size and statistical significance (29 CFR 1607.4(D): greater differences "may not constitute adverse impact where the differences are based on small numbers and are not statistically significant"; https://www.law.cornell.edu/cfr/text/29/1607.4, checked 2026-10-13). Note: the federal executive branch is withdrawing from the Guidelines (U.S. Department of Justice, Office of Legal Counsel slip opinion of 2026-06-09, https://www.justice.gov/olc/media/1444871/dl; OPM interim final rule, 91 Fed. Reg. 48234, 2026-07-31, FR Doc. 2026-15586). LARS does not depend on them; it is a disclosure format for state, local, contractual and EU uses. In the published Libra preprint, an HMDA Black/White origination ratio of 0.8174 had a 95% bootstrap percentile interval of [0.7250, 0.9156] (n=632 in the focal group), so it is consistent with values on both sides of 0.80 and 0.85; the preprint concludes that "a binary label should never be presented without the estimate, sample size, and uncertainty" (Jackson 2026, preprint v1.1, table of focus-group results).
2. **The parameters that decide the verdict are set silently.** The threshold, the comparator group, the outcome definition, the minimum sample size, the handling of unknown or small categories and the treatment of uncertain results each change the answer. In the preprint, moving the threshold from 0.80 to 0.85 changes two selected labels, and a plausible change of outcome definition moves the HMDA ratio from 0.8174 to 0.7162 (same source, abstract). Today nobody has to say who chose these values.

LARS fixes the disclosure, not the policy: every report says what was measured, how uncertain it is, and who chose each rule that turns the measurement into a verdict.

## 2. Definitions

- **Category**: a demographic group (or intersection) for which a rate is computed.
- **n, k**: number of individuals in the category assessed by the system (n) and number receiving the favorable outcome (k).
- **Rate**: k/n. For scoring systems, the **scoring rate** is the share of the category scoring above a stated cut (for NYC LL144, the sample median, per 6 RCNY §5-300).
- **Comparator**: the category whose rate is the denominator of each ratio (e.g., most-selected category).
- **Impact ratio (IR)**: rate(category) / rate(comparator).
- **Threshold (θ)**: the ratio value the report is checked against (e.g., 0.80). LARS treats θ as a **governance parameter**, not a constant.
- **Interval**: a two-sided (1−α) confidence interval [L, U] for the IR.
- **Three-state result** (for each category vs θ):
  - `determinate_below` if U < θ;
  - `determinate_at_or_above` if L ≥ θ;
  - `indeterminate` otherwise (the interval contains θ);
  - `not_estimable` if the IR or its interval can't be computed (e.g., zero events in the comparator, or n below the declared minimum).
- **Governance parameter**: any value that changes the verdict and is not fixed by the data: θ, α, interval method, comparator rule, outcome definition, category scheme, minimum n, exclusion rules, unknown-category handling, data window, burden rule.
- **Burden rule**: the declared consequence of an `indeterminate` result. Machine values: `report_only` (no allocation; the report only describes), `deployer` (the deployer must show the ratio is at or above θ, so indeterminate is treated as unresolved against the deployer), `challenger` (the party alleging disparity must show it is below θ). A `report_only` rule MUST be labelled as such and MUST NOT be presented as a finding of no disparity.

## 3. Normative requirements: counts and estimates

- **R1.** A report MUST disclose n and k for every category assessed, including categories excluded from ratio calculation, and including the "unknown/not reported" category.
- **R2.** A report MUST disclose the outcome definition (what counts as k) and the decision point it measures, in plain language.
- **R3.** A report MUST state the comparator rule and name the comparator category. If the comparator is chosen from the data (e.g., highest rate), the report MUST say so.
- **R4.** A report MUST NOT include the unknown category in the comparator selection or in any category's rate unless it states that it did so and why.
- **R5.** A report MUST give the point IR for each estimable category, to at least three decimal places.

## 4. Normative requirements: uncertainty and the three-state label

- **R6.** A report MUST give a two-sided (1−α) interval for each estimable IR and MUST state both the two-sided level and the resulting one-sided error per determinate claim (α/2). α is a governance parameter: whoever sets it is recorded under §5. Where no one sets it, the reference implementation (`libra-check`) uses α = 0.10 two-sided, i.e. at most 5% error for each `determinate_below` or `determinate_at_or_above` claim (equivalence/non-inferiority logic), and records it as a `tool_default`.
- **R7.** A report MUST name the interval method with a citation. Acceptable methods for a ratio of two independent binomial proportions include Katz log (Katz et al. 1978), Koopman score (Koopman 1984), Miettinen–Nurminen (1985) and MOVER-type intervals, e.g. MOVER with Wilson limits (Donner & Zou 2012; the `libra-check` default). A Wald interval on the raw ratio SHOULD NOT be used. The report MUST say how zero counts were handled.
- **R8.** A report MUST assign each category one of the four states in §2 against each threshold it reports against, and MUST disclose θ.
- **R9.** A report MUST NOT describe an `indeterminate` result as "pass", "compliant", "no adverse impact found" or an equivalent. It MUST NOT describe it as "fail" either. It MUST state the burden rule that applies and who set it (§5).
- **R10.** If the comparator was chosen from the data, or several categories are tested, the report SHOULD state the number of comparisons and MAY additionally report familywise-adjusted states (method named). Unadjusted states remain the primary output unless the governing body says otherwise.
- **R11.** For each `indeterminate` or `not_estimable` category the report SHOULD give the approximate additional sample needed for the interval to exclude θ if the point estimate held (a precision statement, labelled as such and not as a prediction).
- **R9a.** An `indeterminate` or `not_estimable` result MUST NOT be cited, by anyone, as evidence that a system has no disparate impact. A statement that a report "conforms to LARS" says only that disclosure is complete; it MUST NOT be presented as a finding about disparity.
- **R9b.** Every `not_estimable` category MUST be listed with its counts and the reason, and MUST be summarised in the headline as "unresolved", so that small groups are visible rather than silently dropped.
- **R12.** A report MAY add a point-estimate-only label (e.g., the legacy four-fifths reading) but MUST print it next to the three-state label, never instead of it.

## 5. Normative requirements: parameter provenance

- **R13.** For each governance parameter (list in §2), the report MUST record: `name, value, set_by` (person or body), `role` (one of: `community_body`, `regulator`, `auditor`, `vendor`, `employer_deployer`, `researcher`, `standard_default`, `tool_default`, `unattributed`), `process` (e.g., rule text, contract clause, auditor judgment, public hearing), `date`, and `source` (citation or document link).
- **R14.** If a parameter was fixed by law or rule, the report MUST cite the provision. If no law or rule fixes it, the report MUST say so ("unassigned by rule; set by auditor"). A parameter nobody declared MUST still appear, with role `tool_default` or `unattributed`, so the report shows that no accountable party chose it.
- **R15.** If a parameter was changed after the data were first examined, the report MUST disclose the original value, the new value, the reason and who approved the change.
- **R16.** The report MUST identify the software and version used (name, version, commit hash where available) so the numbers can be recomputed.
- **R17.** When the data are test or synthetic data rather than historical data from the deployer, the report MUST say so prominently.
- **R18. Public-body profile.** When a report supports a decision by a public body (approval, procurement, renewal, rulemaking): (a) `burden_rule`, `min_n`, the threshold(s), α and the outcome definition MUST NOT carry role `tool_default`, `vendor`, `employer_deployer` or `unattributed` — the public body or a body it designates sets them; (b) every governance parameter MUST be recorded with a date **before** the outcome data were first examined (pre-registration); a later change is allowed only under R15 and is flagged in the headline; (c) `min_n` MUST NOT exceed 30 per category unless the public body states why (this stops a minimum-n choice from turning every small group into `not_estimable`); (d) results from repeated monitoring looks MUST use intervals valid under repeated looks (e.g. confidence sequences) or state the number of looks and adjust for them.
- **R19. Scores with ties.** For scoring-rate audits, the report MUST state how individuals with scores equal to the cut were handled and the share of individuals tied at the cut; where ties are common (e.g. rubric scores) the report SHOULD state that the nominal error rate may not hold.
- **R20. Harms outside the ratio (SHOULD).** The report SHOULD include a field for known individual-level harm events (e.g. documented wrongful identifications) by category. These are not inputs to the ratio and the three-state label never overrides them.

### Required disclosure record (field list; machine-readable twin in `schemas/`)
`report_id, system, deployer, auditor, decision_point, outcome_definition, selection_rule (rate | scoring_rate), score_cut, category_scheme, categories[{label, n, k, rate, excluded, exclusion_reason}], unknown_category_handling, comparator_rule, comparator_category, thresholds[], alpha, interval_method, zero_handling, ratios[{category, point, lower, upper, state_by_threshold{θ: state}, additional_n_hint}], comparisons_count, adjusted_states (optional), min_n, burden_rule, parameters[{name, value, set_by, role, process, date, source, changed_from}], data_window, data_source (historical | test | synthetic), software{name, version, commit}`

## 6. Recommended practice (non-normative)

- Publish the record as JSON next to the human-readable summary, so third parties can recompute.
- Report against at least two thresholds when θ is not fixed by law (e.g., 0.80 and the value a community or regulator proposes).
- Treat minimum n as a governance choice with its own provenance entry. Don't hide small categories; report them as `not_estimable` with counts.
- When a public body adopts LARS, it should also assign the burden rule itself, so auditors aren't left to choose it.

## 7. Conformance checklist

A report **conforms to LARS v0.1** if every MUST item passes. Conformance means the disclosure is complete. It is never a finding that a system has no disparity (R9a).

| # | Check | Req. | Pass if |
|---|---|---|---|
| 1 | n and k for every category, incl. excluded and unknown | R1 | all present |
| 2 | Outcome definition + decision point stated | R2 | present |
| 3 | Comparator rule + category named; data-driven choice flagged | R3 | present |
| 4 | Unknown category kept out of comparator/rates, or disclosed | R4 | true |
| 5 | Point IR to 3 dp for each estimable category | R5 | present |
| 6 | Interval + α for each estimable IR | R6 | present |
| 7 | Interval method named with citation; zero handling stated | R7 | present |
| 8 | Four-valued state per category per threshold; θ disclosed | R8 | present |
| 9 | No "pass/compliant/fail" wording on an indeterminate result; burden rule + setter stated | R9 | true |
| 10 | Provenance record for every governance parameter | R13 | all params in §2 covered |
| 11 | Legal source cited or "unassigned by rule" stated | R14 | per parameter |
| 12 | Post-hoc parameter changes disclosed | R15 | none, or disclosed |
| 13 | Software + version | R16 | present |
| 14 | Test/synthetic data flagged | R17 | true or n/a |
| 15 | No "pass/no disparate impact" claim rests on indeterminate/not-estimable results; not-estimable categories listed with counts | R9a, R9b | true |
| 16 | Public-body profile: no verdict-relevant parameter set by tool default, vendor or deployer; parameters dated before data access; min_n ≤ 30 or justified; repeated looks handled | R18 | true, or n/a if no public-body decision |
| 17 | Tie handling stated for scoring rates | R19 | true or n/a |

SHOULD items (R10, R11, Wald avoidance in R7) are reported as "followed / not followed" and don't affect conformance.

## 8. Mapping to existing requirements (where LARS slots in)

| Instrument | What it already asks | What LARS adds | Status |
|---|---|---|---|
| NYC 6 RCNY §5-301/§5-303 (LL144 bias audit + published summary) | selection/scoring rates and impact ratios per category; number of individuals in "unknown" category; data source and dates | n and k per category, interval, three-state label, comparator rule, parameter provenance, burden rule | 6 RCNY §5-300 to §5-304 (DCWP rule, effective 2023-07-05) |
| 29 CFR 1607.4(D) (UGESP) | four-fifths rule of thumb plus statistical significance and sample size considerations | a standard way to report both at once | still codified; federal withdrawal under way (see note in §1) |
| Cal. CRD regs, 2 CCR §11009(f) (eff. 2025-10-01) | "quality, efficacy, recency, and scope" of anti-bias testing and its results are relevant evidence | a checkable definition of what a high-quality, disclosed test result looks like | 2 CCR §11009(f) |
| NYC LL 193/2025 "basic compliance standards" (fairness) for agency AI | fairness standards to be set by rule; no metric | candidate rule content | NYC Local Law 193 of 2025; no metric set yet |
| Detroit CIOGS §17-5-452(d) | Council "disparate impact" determination; no standard (*Eagan v. Detroit*, Mich. Ct. App. No. 366454, 2025-10-09) | the evidence standard | Detroit City Code §17-5-452(d) (Ord. 2021-17) |
| OMB M-25-21 §4(b) / M-25-22 §4.d (federal) | pre-deployment testing, ongoing monitoring for adverse impacts, reproducible vendor testing | the reporting format for the disparity part | OMB M-25-21, M-25-22 |
| ISO/IEC 42005:2025, 42001:2023, TS 12791:2024; IEEE 7003-2024, IEEE 3198-2025 (ML fairness evaluation) | process requirements / bias metrics and treatment | a disclosure record usable inside those processes | not yet reviewed against these texts (paywalled); IEEE 3198 is the closest comparator |
| EU AI Act Art. 10(2)(f)–(g), Art. 72, Art. 27 FRIA (Annex III now applies from 2027-12-02 per Reg. (EU) 2026/1744); prEN 18283 (bias) in drafting | examine/detect/mitigate bias; monitor | an output format for monitoring results | fit not yet assessed |

## 9. Open questions (for counsel / reviewers before v0.2)

1. Default α and default interval method: v0.1 requires disclosure and uses one reference default everywhere (α = 0.10 two-sided, i.e. ≤5% error per determinate claim; MOVER-Wilson). Should a public body be required to set α itself (R18)? v0.1: yes, for public-body use.
2. Intersectional categories multiply comparisons; is the R10 SHOULD enough?
3. Does labelling a result `determinate_below` create litigation exposure for deployers that discourages voluntary adoption? (Likely yes.)
4. Continuous monitoring: how to report sequential looks without inflating error (SHOULD reference group-sequential or always-valid intervals in v0.2).
