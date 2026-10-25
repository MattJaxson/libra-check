"""libra-check command line.

  libra-check analyze counts.csv [--theta 0.8 --theta 0.85] [--alpha 0.10] [--provenance prov.json]
                      [--meta meta.json] [--preset ll144] [--exclude-small 0.02] [--out report.json]
                      [--md report.md] [--html report.html] [--require-provenance]
  libra-check ll144 applicants.csv (--selected-col selected | --score-col score) [--sex-col sex --race-col race] ...
  libra-check conform report.json
  libra-check validate report.json        (JSON Schema validation)
  libra-check provenance-template > prov.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .conform import check, to_text
from .core import InputError, analyze
from .io import load_counts, load_individuals
from .provenance import GOVERNANCE_DEFAULTS, ProvenanceError, load_provenance
from .render import to_html, to_markdown

SCHEMA_PATH = Path(__file__).parent / "schema" / "libra-audit-report-0.1.schema.json"


def _common(p):
    p.add_argument("--theta", type=float, action="append", help="threshold(s); repeatable; first is primary")
    p.add_argument("--alpha", type=float, help="two-sided error level of the interval (default 0.10 = 5%% per bound)")
    p.add_argument("--method", dest="interval_method", choices=["mover_wilson", "koopman", "miettinen_nurminen", "katz_log"])
    p.add_argument("--comparator", dest="comparator_rule", help="max_rate_eligible | max_rate_all | fixed:<category>")
    p.add_argument("--exclude-small", dest="small_category_exclusion", type=float,
                   help="exclude categories below this share of known individuals (LL144 option: 0.02)")
    p.add_argument("--min-n", dest="min_n", type=int)
    p.add_argument("--burden", dest="burden_rule", choices=["report_only", "deployer", "challenger"])
    p.add_argument("--multiplicity", choices=["none", "bonferroni"])
    p.add_argument("--outcome", dest="outcome_definition")
    p.add_argument("--data-window", dest="data_window")
    p.add_argument("--category-scheme", dest="category_scheme")
    p.add_argument("--selection-adjustment", dest="selection_adjustment", choices=["pairwise_min", "none"],
                   help="account for the data-selected comparator (default pairwise_min); 'none' = conditional")
    p.add_argument("--exclusion-base", dest="exclusion_base", choices=["known", "all_assessed"])
    p.add_argument("--estimand", choices=["process", "finite_population"])
    p.add_argument("--precommitted", help="parameter hash published before analysis (from `libra-check commit`)")
    p.add_argument("--provenance", help="parameter provenance record (JSON)")
    p.add_argument("--meta", help="report context JSON: system, deployer, auditor, decision_point, data_source")
    p.add_argument("--preset", choices=["none", "ll144"], default=None)
    p.add_argument("--require-provenance", action="store_true",
                   help="fail if any governance parameter is a tool default or has no declared setter")
    p.add_argument("--power", type=float, default=0.80)
    p.add_argument("--no-power", action="store_true", help="skip precision computations (faster)")
    p.add_argument("--out", help="write JSON report here (default: stdout)")
    p.add_argument("--md", help="write Markdown report")
    p.add_argument("--html", help="write HTML report")


CLI_KEYS = ("interval_method", "comparator_rule", "small_category_exclusion", "min_n", "burden_rule",
            "multiplicity", "outcome_definition", "data_window", "category_scheme", "alpha",
            "selection_adjustment", "exclusion_base", "estimand")


def _cli_values(args, extra_cli=None):
    cli = {k: getattr(args, k, None) for k in CLI_KEYS}
    cli["thresholds"] = args.theta
    cli.update(extra_cli or {})
    return cli


def _run(args, units, meta, extra_cli=None, post=None):
    cli = _cli_values(args, extra_cli)
    if args.meta:
        meta = {**meta, **json.loads(Path(args.meta).read_text())}
    rep = analyze(units, meta, cli=cli, declared=load_provenance(args.provenance), preset=args.preset,
                  strict=args.require_provenance, power=args.power, compute_power=not args.no_power,
                  precommitted_hash=args.precommitted)
    if post:
        post(rep, cli, meta)
    js = json.dumps(rep, indent=1, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(js)
    if args.md:
        Path(args.md).write_text(to_markdown(rep))
    if args.html:
        Path(args.html).write_text(to_html(rep))
    if not args.out:
        print(js)
    else:
        s = rep["summary"]["by_threshold"]
        for t, v in s.items():
            c = v["states"]
            print(f"theta={t}: below={c['determinate_below']} indeterminate={c['indeterminate']} "
                  f"at_or_above={c['determinate_at_or_above']} not_estimable={c['not_estimable']}")
        for w in rep["warnings"]:
            print(f"warning {w['code']}: {w['message']}", file=sys.stderr)
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(prog="libra-check", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"libra-check {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="aggregate counts -> report")
    a.add_argument("counts")
    _common(a)
    b = sub.add_parser("ll144", help="individual-level data -> LL144 counts -> report")
    b.add_argument("data")
    b.add_argument("--sex-col", default="sex")
    b.add_argument("--race-col", default="race")
    b.add_argument("--selected-col")
    b.add_argument("--score-col")
    b.add_argument("--no-intersectional", action="store_true")
    b.add_argument("--counts-out", help="also write the derived counts JSON")
    _common(b)
    s = sub.add_parser("sensitivity", help="states across a grid of legal parameter choices (forking-paths view)")
    s.add_argument("counts")
    s.add_argument("--json", action="store_true")
    m = sub.add_parser("commit", help="print the parameter hash to publish BEFORE seeing the data")
    m.add_argument("--provenance", required=True)
    m.add_argument("--preset", choices=["none", "ll144"], default=None)
    c = sub.add_parser("conform", help="LARS v0.1 §7 conformance check of a report JSON")
    c.add_argument("report")
    c.add_argument("--json", action="store_true")
    v = sub.add_parser("validate", help="validate a report against the JSON Schema")
    v.add_argument("report")
    sub.add_parser("provenance-template", help="print a provenance record template")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "analyze":
            units, meta = load_counts(args.counts)
            _run(args, units, meta)
        elif args.cmd == "ll144":
            units, info = load_individuals(args.data, args.sex_col or None, args.race_col or None,
                                           args.selected_col, args.score_col, intersectional=not args.no_intersectional)
            extra = {"selection_rule": "scoring_rate" if args.score_col else "rate",
                     "score_cut": "median_full_sample" if args.score_col else None}
            if args.counts_out:
                Path(args.counts_out).write_text(json.dumps({"meta": {"ll144_derivation": info}, "units": units}, indent=1))
            if args.preset is None:
                args.preset = "ll144"
            alt_units = info.pop("_alt_units", None)

            def post(rep, cli, meta):
                if args.no_intersectional and args.preset == "ll144":
                    rep["warnings"].append({"code": "INTERSECTIONAL_REQUIRED", "message":
                                            "6 RCNY §5-301(b)(3)/(c)(4) require intersectional categories; run without --no-intersectional"})
                if alt_units:
                    alt = analyze(alt_units, meta, cli=cli, declared=load_provenance(args.provenance), preset=args.preset,
                                  compute_power=False)
                    diff = []
                    for u0, u1 in zip(rep["units"], alt["units"]):
                        a = {r["category"]: r["state_by_threshold"] for r in u1["ratios"]}
                        for r in u0["ratios"]:
                            if a.get(r["category"]) != r["state_by_threshold"]:
                                diff.append(f"{u0['dimension']}: {r['category']}")
                    share = info["ties_at_median"] / max(info["n_scored"], 1)
                    rep["cut_sensitivity"] = {"alt_cut": info["alt_cut"], "ties_at_median": info["ties_at_median"],
                                              "tie_share": round(share, 4), "categories_with_different_states": diff}
                    if diff or share > 0.02:
                        rep["warnings"].append({"code": "CUT_UNSTABLE", "message":
                                                f"{info['ties_at_median']} scores ({100 * share:.1f}%) sit exactly at the median; "
                                                f"with the adjacent cut (score >= median) states change for {len(diff)} "
                                                f"categories: {diff[:10]}"})

            rep = _run(args, units, {"ll144_derivation": info}, extra, post=post)
            if info.get("ties_at_median"):
                print(f"note: {info['ties_at_median']} scores equal the median and are not counted as 'above'", file=sys.stderr)
            return 0 if rep else 1
        elif args.cmd == "commit":
            from .core import params_sha256
            from .provenance import resolve
            params = resolve({}, load_provenance(args.provenance), preset=args.preset)
            print(params_sha256(params))
        elif args.cmd == "sensitivity":
            from .sensitivity import grid, to_text as sens_text
            units, meta = load_counts(args.counts)
            res = grid(units, meta)
            print(json.dumps(res, indent=1) if args.json else sens_text(res))
        elif args.cmd == "conform":
            res = check(json.loads(Path(args.report).read_text()))
            print(json.dumps(res, indent=1) if args.json else to_text(res))
            return 0 if res["conforms"] else 2
        elif args.cmd == "validate":
            import jsonschema
            schema = json.loads(SCHEMA_PATH.read_text())
            errs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(json.loads(Path(args.report).read_text())),
                          key=lambda e: list(e.path))
            for e in errs:
                print(f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}")
            print("valid" if not errs else f"{len(errs)} schema error(s)")
            return 0 if not errs else 2
        elif args.cmd == "provenance-template":
            tpl = {"parameters": [{"name": k, "value": v, "set_by": "<person or body>",
                                   "role": "<community_body|regulator|auditor|vendor|employer_deployer|researcher|standard_default>",
                                   "process": "<rule text | contract clause | auditor judgment | public hearing | ...>",
                                   "date": "YYYY-MM-DD", "source": "<citation, or 'unassigned by rule'>"}
                                  for k, v in GOVERNANCE_DEFAULTS.items()]}
            print(json.dumps(tpl, indent=1))
    except (InputError, ProvenanceError) as e:
        print(f"libra-check: error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
