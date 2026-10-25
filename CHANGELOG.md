# Changelog

All notable changes to libra-check. Dates are ISO 8601.

## 0.2.0 (first public release, 2026-10-25)

First public release under Apache-2.0. Functionally identical to the internal 0.2.0 build of 2026-10-13.

Main features (several were added after an internal red-team review of the 0.1 build):
- Comparator-aware default (`selection_adjustment = pairwise_min`): every category, the comparator
  included, is tested against all others with Bonferroni over the other categories. The conditional
  state (comparator treated as fixed) is reported alongside.
- Guard against a determinate state that contradicts the point estimate; order-invariant results;
  explicit handling of scores tied at the median cut.
- "Indeterminate is not a pass" rule enforced in all renderings (LARS R9, R9a).
- `commit` command: hash a parameter file before seeing data (pre-registration).
- `estimand` (`process` | `finite_population`) and `data_scope` (`own` | `pooled:<J>`) fields with
  warnings.
- `sensitivity` command: verdicts across defensible parameter configurations.
- `validation/coverage_exact.py`: exact-enumeration coverage of every interval method.

Changed:
- README now states the worst-case error of MOVER-R Wilson on the "at or above" side (9.1% against a
  5% nominal rate, small focal groups) instead of "about 8%".

Release packaging (no code changes):
- Apache-2.0 `LICENSE` and `NOTICE`; `CITATION.cff`; `CONTRIBUTING.md`; package metadata.

Known issue:
- `software.commit` in a report is read with `git rev-parse` from the installed package's directory.
  If the package is installed inside some other git working tree, the reported commit belongs to that
  tree. Treat the commit field as informative only when running from a clone of this repository.

## 0.1.0 (internal, 2026-10-12)

Initial internal build: impact ratios, MOVER-R Wilson / Koopman / Miettinen–Nurminen / Katz intervals,
three-state classification, LARS v0.1 JSON/Markdown/HTML output, provenance record, LL144 mode.
