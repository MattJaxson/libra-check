# Contributing to libra-check

Thank you for looking. This is a one-person, unfunded project, so replies may take a few days.

## Most useful

1. **Bug reports with a minimal input.** Attach the smallest `counts.csv` (and `prov.json`, if
   relevant) that reproduces the problem, the command you ran, and what you expected. Do not upload
   individual-level personal data; aggregate counts are enough.
2. **Interval or coverage problems.** If you find a design where an interval's error rate is worse
   than `validation/out/coverage_summary.md` says, please report the design (n, k, comparator rate).
3. **Mismatches with a published audit or rule text.** Cite the document and section.

## Pull requests

- Open an issue first for anything beyond a small fix, so we can agree on the approach.
- Run the tests: `python -m pytest -q`. All tests must pass. Add a test for every bug fix.
- Keep the scope rules: the tool never reports an `indeterminate` result as a pass, never makes a
  legal determination, and labels every parameter nobody declared as a tool default.
- Changes to the report format must be matched by a change to the LARS specification (`lars-spec`)
  and the JSON schemas in `src/libra_check/schema/`.

## License of contributions

By submitting a contribution you agree that it is licensed under the Apache License 2.0, the same
license as the project (Apache-2.0 §5). Please only submit work you have the right to license.

## Conduct

Be specific and be kind. Criticism of the method is welcome; that is how it got better.
