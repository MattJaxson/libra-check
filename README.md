# libra-check

Impact ratios with uncertainty, a three-state verdict, and a record of who chose every rule.

`libra-check` takes per-group counts (how many people a system assessed, how many got the favorable
outcome) and writes a report in the format of the Libra Audit Reporting Standard (LARS) v0.1: JSON for
machines, Markdown or HTML for people. It is meant for auditors, public bodies, researchers and journalists
who work from published or raw counts. **It makes no legal determination.**

- Version: 0.2.0 (alpha). The report format and command-line flags may still change before 1.0.
- License: Apache-2.0 (see `LICENSE` and `NOTICE`).
- Specification: LARS v0.1, bundled in [`spec/`](spec/) (CC BY 4.0).
- Author: Matthew Jackson, independent researcher, Detroit, Michigan. Unfunded; no vendor ties.

## What it does

For each category in each dimension (sex, race/ethnicity, intersectional, and so on):

1. **Impact ratio** = category rate / comparator rate. The comparator is the highest-rate eligible
   category (the NYC Local Law 144 definition, 6 RCNY §5-300) or a fixed category you declare.
2. **Interval** for the ratio. MOVER-R with Wilson limits by default; Koopman and Miettinen–Nurminen
   score intervals are available; Katz log is available only as a flagged sensitivity check.
3. **State** at each declared threshold θ:
   - `determinate_below`: the whole interval is under θ
   - `determinate_at_or_above`: the whole interval is at or over θ
   - `indeterminate`: the data fit values on both sides of θ. This is neither a pass nor a fail.
   - `not_estimable`: comparator rate 0, or n below a declared minimum
4. **Comparator chosen from the data.** By default (`selection_adjustment = pairwise_min`) every
   category, the comparator included, is tested against all others: IR_g = min(1, min_h p_g/p_h),
   lower = min_h L(g,h), upper = min_h U(g,h), with Bonferroni over the other categories. The
   conditional state (comparator treated as fixed) is reported alongside. Also: a rounding envelope
   when counts were rebuilt from rounded percentages, Bonferroni-adjusted states, and a stability check
   for scores tied at the median cut.
5. **Precision statement**: the band of true ratios this sample size cannot tell apart from θ, and
   roughly how much more data would resolve an indeterminate result if the point estimates held.
   This is labelled as a precision statement, not a prediction.
6. **Parameter provenance**: θ, α, comparator rule, outcome definition, minimum n, exclusions,
   unknown-category handling, data window and the burden rule each carry `set_by`, `role`, `process`,
   `date` and `source`. Anything nobody declared is labelled a tool default, so the report shows that
   no accountable party chose it.

LL144 specifics (checked against the adopted DCWP rule text on 2026-10-13): scoring rate = share scoring
**above the median of the full sample** (§5-301(c)(1)); individuals in the unknown category are counted
and reported but never enter a ratio (§5-301(b)(5)); the optional under-2% exclusion is applied only if
declared, and excluded categories are still reported with n and rate (§5-301(d)).

## What is not new

The statistics in this package are not a methods contribution, and the package should not be cited as one.

- Significance tests and confidence intervals for the adverse impact ratio go back at least to
  Morris & Lobsenz (2000), *Personnel Psychology* 53(1), doi:10.1111/j.1744-6570.2000.tb00195.x.
  The 1978 Uniform Guidelines (29 CFR 1607.4(D)) already caution that the four-fifths rule is
  unreliable for small numbers.
- Courey & Oswald (2025), *Psychology, Public Policy, and Law* 31(2):134–146, doi:10.1037/law0000451,
  give a Bayesian adverse impact ratio with priors ranging from plaintiff-favoring to
  defendant-favoring. That is the closest academic overlap with the burden-rule idea here.
- General fairness toolkits already compute intervals for disparity ratios. For example, Fairlearn's
  `MetricFrame` produces percentile-bootstrap intervals for ratios and differences (`n_boot`,
  `ci_quantiles`); see https://fairlearn.org/main/user_guide/assessment/confidence_interval_estimation.html.
- The interval methods are standard: Donner & Zou (2012), Newcombe (2016), Wilson (1927),
  Koopman (1984), Miettinen & Nurminen (1985), Katz et al. (1978). Full citations appear in every report.

What this package adds is narrower: a **disclosure format** (LARS) in which an uncertain result cannot
be reported as a pass, every verdict-changing parameter has a named owner, and the consequence of an
indeterminate result (the burden rule) must be declared by someone, plus a checker for that format.

## Install and run

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[test]'
.venv/bin/libra-check provenance-template > prov.json      # fill in who chose what
.venv/bin/libra-check analyze counts.csv --provenance prov.json --meta meta.json \
     --out report.json --md report.md --html report.html
.venv/bin/libra-check conform report.json                  # LARS v0.1 §7 checklist
.venv/bin/libra-check validate report.json                 # JSON Schema
.venv/bin/libra-check commit --provenance prov.json        # hash to publish BEFORE seeing data
.venv/bin/libra-check sensitivity counts.csv               # do verdicts depend on parameter choices?
# individual-level LL144 data (one row per applicant):
.venv/bin/libra-check ll144 applicants.csv --score-col score --sex-col sex --race-col race \
     --exclude-small 0.02 --out report.json --md report.md
```

`counts.csv`: columns `category,n,k` (or `rate` instead of `k`, for example from a published summary),
optional `dimension`, `unknown`. Rows named `Unknown` or `Missing/Unknown` are treated as the unknown
category. `meta.json`: `system`, `deployer`, `auditor`, `decision_point`, `data_source`
(`historical|test|synthetic`).

Key flags: `--theta` (repeatable), `--alpha` (two-sided; default 0.10, i.e. a nominal 5% error per
determinate claim), `--comparator fixed:<category>`, `--min-n`, `--burden deployer|challenger|report_only`,
`--multiplicity bonferroni`, `--require-provenance` (refuse to run on undeclared or unattributed parameters).

Python API: `from libra_check import analyze`.

## Worked examples (public data)

`examples/` has two worked examples taken from the author's earlier Libra preprint v1.1
(doi:10.5281/zenodo.23328063): a Michigan single-lender HMDA filing and the ProPublica COMPAS Broward
County data. For example, the HMDA Black/White origination ratio is 0.817 with a 95% interval of
[0.726, 0.916], which is `indeterminate` at both 0.80 and 0.85. The example reports were generated
before this repository existed, so the `software.commit` field in them points to a private working
tree; regenerate them to get a commit hash from this repository.

## Tests

```bash
.venv/bin/python -m pytest -q        # 78 tests
```

The tests check the intervals against statsmodels and an independent MOVER-R implementation, reproduce
DCWP's own published example tables, and cover zeros, k = n, tiny groups, ties, unknown categories, the
2% rule, rounded rates, schema validity, conformance and the CLI.

`validation/coverage_exact.py` computes exact (enumerated) coverage of every interval method over 840
designs (about 7 minutes; needs pandas). Its summary is in `validation/out/coverage_summary.md`.

## Known limits (read before relying on it)

- **The nominal error rate is not exact for small groups.** With the default α = 0.10, each
  determinate claim has a nominal 5% error. Exact enumeration shows that MOVER-R Wilson's error on the
  "at or above" side reaches **9.1% in the worst case** (median 5.25%; 13% of designs exceed nominal by more
  than one percentage point). Every one of those designs has a small focal group or a low selection rate
  (worst case: focal n = 10, comparator n = 200, comparator rate 0.10). The error on the "below" side never
  exceeds 5.8%. So the excess error runs in the direction that favours the deployer. Katz log is worse
  and is flagged as sensitivity-only.
- **The comparator-aware default leaves most intersectional results indeterminate.** The default
  (`pairwise_min`) keeps the per-claim error near nominal even though the comparator is chosen from the
  data, and it gives the comparator itself a state. The price is power. In the author's synthetic
  benchmark (LL144-Bench v0, not yet released), at exact parity the point-estimate four-fifths rule
  falsely flagged at least one group in 99.4% of intersectional audits, against 2.6% for libra-check.
  But libra-check made **no call at all on 97% of intersectional categories** and missed 85% of groups
  whose true ratio was below 0.80. With typical LL144 sample sizes, most intersectional categories will
  come back `indeterminate`. That is an honest description of the data, not a pass, and it will
  frustrate anyone hoping for a verdict.
- **The census objection is open.** An LL144 audit covers every applicant in its window, so one can
  argue that its rates are a finite-population fact and that calling a ratio of 0.76 "indeterminate"
  invents uncertainty and gives employers cover. libra-check treats the counts as a draw from the
  hiring process the tool will keep applying (the `estimand = process` default; US courts have treated
  full applicant-flow data this way, e.g. *Hazelwood School District v. United States*, 433 U.S. 299
  (1977), fn. 17). You can declare `estimand = finite_population`: the point ratio is then reported as
  exact and the states are shown only as an "inferential view". Which estimand is right is a governance
  question, not a statistical one, and this package does not settle it.
- **Intervals assume binomial counts** (independent individuals, a stable process). For median-split
  scoring rates the cut is estimated from the same data, which this package does not correct for.
- **Pooled multi-employer data** (`data_scope: pooled`) measure the pool, not the deployer. No method
  recovers the audited employer's own ratio from pooled data; the report warns but cannot fix it.
- **A provenance record is self-reported.** The tool makes undeclared choices visible and can hash a
  parameter file before analysis (`commit`). It cannot prove that a parameter was fixed before anyone
  looked at the data.
- **`indeterminate` is a statement about evidence, not a safe harbor.** What it triggers is the burden
  rule, which a governing body, not the tool, should set.
- No field use yet. The package has been tested on public and synthetic data only.

## Citing

See `CITATION.cff`. Please also cite Morris & Lobsenz (2000) for the underlying statistics.

## Contributing

See `CONTRIBUTING.md`. Bug reports with a minimal `counts.csv` are the most useful contribution.
