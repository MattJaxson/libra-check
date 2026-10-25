# LARS: Libra Audit Reporting Standard (v0.1, draft for comment)

**A disclosure format for group-disparity results (impact ratios) that makes uncertainty and parameter
ownership visible.** Every LARS report says what was measured, how uncertain it is, and who chose each rule
that turns the measurement into a verdict. An uncertain result can never be reported as a pass.

| File | What |
|---|---|
| `LARS-v0.1.md` | The normative specification (RFC 2119 keywords) |
| `CONFORMANCE_CHECKLIST.md` | The §7 checklist as a fill-in form |
| `schemas/libra-audit-report-0.1.schema.json` | JSON Schema (draft 2020-12) for a LARS report record |
| `schemas/libra-provenance-record-0.1.schema.json` | JSON Schema for the parameter provenance record |

Reference implementation: [`libra-check`](https://github.com/MattJaxson/libra-check) (Apache-2.0) emits
and checks LARS v0.1 records.

## What LARS is and is not

- It **is** a disclosure format that a regulator, public body, buyer or auditor can adopt by reference.
- It **does not** set a legal threshold, define "fair", or say what any law requires.
- It **is not** a new statistical method. Intervals for the adverse impact ratio date at least to
  Morris & Lobsenz (2000), and general toolkits such as Fairlearn already compute disparity-ratio intervals.
  LARS adds the disclosure rule, named parameter owners and a declared burden rule for uncertain results.
- It has **not** been adopted or endorsed by any public body. A clause-by-clause comparison with the
  CDT et al. Civil Rights Standards (2022), IEEE 3198-2025 and ISO/IEC TS 12791:2024 is still pending.

## Status and versioning

v0.1 is a draft for comment. Breaking changes are possible in v0.2. Schema `$id`s currently use the
reserved `libra.invalid` host as placeholders; they will move to a stable URL in a later version.

## Comment

Open an issue. Especially useful: overlaps with existing standards, cases where a MUST is unworkable
for a real audit, and legal-exposure concerns (§9, question 3).

## License and citation

CC BY 4.0 (see `LICENSE.md`). Cite as: Matthew Jackson (2026). *Libra Audit Reporting Standard (LARS)
v0.1, draft for comment.* See `CITATION.cff`.
