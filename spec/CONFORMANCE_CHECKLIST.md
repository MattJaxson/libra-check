# LARS v0.1 conformance checklist (fill-in form)

A report **conforms to LARS v0.1** if every MUST item below passes. Conformance means the disclosure is
complete. It is **never** a finding that a system has no disparity (R9a).

The reference implementation can run most of these checks automatically: `libra-check conform report.json`
(and `libra-check validate report.json` for the JSON Schema).

Report checked: ______________________  Checked by: ______________  Date: __________

| # | Check | Req. | Pass if | Pass / Fail / n.a. | Notes |
|---|---|---|---|---|---|
| 1 | n and k for every category, including excluded and unknown | R1 | all present | | |
| 2 | Outcome definition and decision point stated | R2 | present | | |
| 3 | Comparator rule and category named; data-driven choice flagged | R3 | present | | |
| 4 | Unknown category kept out of comparator and rates, or disclosed | R4 | true | | |
| 5 | Point IR to 3 decimal places for each estimable category | R5 | present | | |
| 6 | Interval and α for each estimable IR | R6 | present | | |
| 7 | Interval method named with citation; zero handling stated | R7 | present | | |
| 8 | Four-valued state per category per threshold; θ disclosed | R8 | present | | |
| 9 | No "pass / compliant / fail" wording on an indeterminate result; burden rule and its setter stated | R9 | true | | |
| 10 | Provenance record for every governance parameter | R13 | all parameters in §2 covered | | |
| 11 | Legal source cited, or "unassigned by rule" stated | R14 | per parameter | | |
| 12 | Post-hoc parameter changes disclosed | R15 | none, or disclosed | | |
| 13 | Software name and version | R16 | present | | |
| 14 | Test or synthetic data flagged | R17 | true or n.a. | | |
| 15 | No "pass / no disparate impact" claim rests on indeterminate or not-estimable results; not-estimable categories listed with counts | R9a, R9b | true | | |
| 16 | Public-body profile: no verdict-relevant parameter set by tool default, vendor or deployer; parameters dated before data access; min_n ≤ 30 or justified; repeated looks handled | R18 | true, or n.a. if no public-body decision | | |
| 17 | Tie handling stated for scoring rates | R19 | true or n.a. | | |

SHOULD items (reported as followed / not followed; they do not affect conformance):

| Item | Req. | Followed? |
|---|---|---|
| Number of comparisons stated; familywise-adjusted states (method named) | R10 | |
| Additional-sample precision statement for indeterminate / not-estimable categories | R11 | |
| No Wald interval on the raw ratio | R7 | |
| Known individual-level harm events recorded by category | R20 | |

Result: [ ] conforms to LARS v0.1   [ ] does not conform (failed items: ______ )
