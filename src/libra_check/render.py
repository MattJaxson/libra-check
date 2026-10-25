"""Human-readable rendering of a libra-check report (Markdown and self-contained HTML)."""
from __future__ import annotations

import html
import re

STATE_TEXT = {
    "determinate_below": "BELOW θ (determinate)",
    "determinate_at_or_above": "AT/ABOVE θ (determinate)",
    "indeterminate": "INDETERMINATE",
    "not_estimable": "NOT ESTIMABLE",
}


def _f(x, nd=3):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def _st(s):
    return STATE_TEXT.get(s, s)


def _burden_text(rep):
    p = next((p for p in rep.get("parameters", []) if p["name"] == "burden_rule"), None)
    if p is None or p.get("role") in ("tool_default", "unattributed"):
        return ("**No burden rule assigned: indeterminate results are unresolved, not passes.**")
    return f"{rep['burden_rule']} (set by {p['set_by']}, {p['role']})"


def to_markdown(rep: dict) -> str:
    th = [f"{t:g}" for t in rep["thresholds"]]
    t0 = th[0]
    lvl = 100 * (1 - rep["alpha"])
    L = [f"# Impact-ratio report — {rep.get('system') or 'unnamed system'}", "",
         f"Report `{rep['report_id']}` · generated {rep['generated_at']} · {rep['software']['name']} "
         f"{rep['software']['version']} · LARS v{rep['lars_version']}", ""]
    if rep["data_source"] in ("test", "synthetic"):
        L += [f"> **{rep['data_source'].upper()} DATA.** These numbers do not describe the system's real use.", ""]
    L += ["| | |", "|---|---|",
          f"| Deployer | {rep.get('deployer') or '—'} |", f"| Auditor | {rep.get('auditor') or '—'} |",
          f"| Decision point | {rep.get('decision_point') or '—'} |",
          f"| Outcome definition (what counts as k) | {rep['outcome_definition']} |",
          f"| Rate type | {rep['selection_rule']}{' (cut: ' + str(rep['score_cut']) + ')' if rep.get('score_cut') else ''} |",
          f"| Data source / window | {rep['data_source']} / {rep['data_window']} |",
          f"| Comparator rule | {rep['comparator_rule']} |",
          f"| Threshold(s) θ | {', '.join(th)} |",
          f"| Interval | two-sided {lvl:g}% ({rep['alpha_per_bound']:g} error per bound), {rep['interval_method']} |",
          f"| Minimum n | {rep['min_n'] if rep['min_n'] is not None else 'none declared'} |",
          f"| Burden rule for indeterminate results | {_burden_text(rep)} |",
          f"| Comparator selection accounted for | {rep.get('selection_adjustment', 'none')} |",
          f"| Estimand / data scope | {rep.get('estimand', 'process')} / {rep.get('data_scope', 'own')} |", "",
          "> **Not a legal finding.** This report describes statistical evidence relative to declared parameters. "
          "NYC Local Law 144 and its rules set no impact-ratio threshold.", "",
          "## How to read this", "",
          f"Each impact ratio (IR) is a category's rate divided by the comparator's rate, shown with a {lvl:g}% interval. "
          "**Determinate below**: the whole interval is under θ. **Determinate at/above**: the whole interval is at or "
          "over θ. **Indeterminate**: the data are consistent with values on both sides of θ — this is *neither a pass "
          "nor a fail*; what follows from it is set by the declared burden rule. **Not estimable**: the ratio cannot be "
          "computed (zero comparator rate, or n under the declared minimum).", "",
          "## Summary", "", "| θ | below | indeterminate | at/above | not estimable | familywise below | point estimate below θ |",
          "|---|---|---|---|---|---|---|"]
    for k, s in rep["summary"]["by_threshold"].items():
        c = s["states"]
        L.append(f"| {k} | {c['determinate_below']} | {c['indeterminate']} | {c['determinate_at_or_above']} | "
                 f"{c['not_estimable']} | {s['adjusted_states']['determinate_below']} | {s['point_below_count']} |")
    L += ["", f"{rep['comparisons_count']} comparisons in {rep['summary']['units']} unit(s). Familywise column: "
          "Bonferroni over all comparisons.", ""]
    for u in rep["units"]:
        L += [f"## Unit: {u['dimension']}", "",
              f"Comparator: **{u['comparator_category']}** (rate {_f(u['comparator_rate'], 4)})"
              + ((" — chosen from the data as the highest rate; intervals account for that choice (every category, "
                  "the comparator included, is tested against all others)." if rep.get("selection_adjustment") == "pairwise_min"
                  else " — chosen from the data as the highest rate; intervals treat it as fixed (conditional).")
                 if u["comparator_data_selected"] else " — fixed in advance.")
              + f" Known individuals: {u['total_known_n']}; unknown category: {u['unknown_n']} (reported, not in ratios).", "",
              "| Category | n | k | rate | share of known | status |", "|---|---|---|---|---|---|"]
        for c in u["categories"]:
            status = c["exclusion_reason"] if c["excluded"] else "included"
            if c.get("k_reconstructed"):
                status += f"; k reconstructed (range {c['k_bounds'][0]}–{c['k_bounds'][1]})"
            L.append(f"| {c['label']} | {c['n']} | {_f(c['k'])} | {_f(c['rate'], 4)} | {_f(c['share_of_known'], 3)} | {status} |")
        L += ["", "| Category | IR | interval | " + " | ".join(f"state @ {t}" for t in th)
              + f" | point-only reading @ {t0} | ignoring comparator selection @ {t0} | resolvable band (80% power) |",
              "|---|---|---|" + "---|" * len(th) + "---|---|---|"]
        for r in u["ratios"]:
            up = "∞" if r.get("upper_infinite") else _f(r["upper"])
            pr = r.get("conditional", {}).get("state_by_threshold", {}).get(t0)
            band = r.get("precision")
            bt = "—" if not band else (f"below if ≤{_f(band['flags_below_if_true_ir_at_most'])}; "
                                       f"at/above if ≥{_f(band['certifies_at_or_above_if_true_ir_at_least'])}")
            L.append(f"| {r['category']}{' (comparator)' if r.get('is_comparator') else ''} | {_f(r['point'])} | [{_f(r['lower'])}, {up}] | "
                     + " | ".join(_st(r['state_by_threshold'][t]) for t in th)
                     + f" | {r['point_label_by_threshold'][t0] or '—'} | {_st(pr) if pr else '—'} | {bt} |")
        notes = [r for r in u["ratios"] if r.get("additional_n_hint") and r["additional_n_hint"].get("scale_factor")]
        if notes:
            L += ["", "Precision statements (not predictions): if both point rates held, the interval would exclude "
                  f"θ={t0} at about:"]
            for r in notes:
                h = r["additional_n_hint"]
                L.append(f"- {r['category']}: {h['scale_factor']:g}× the current sample "
                         f"(focal n ≈ {h['focal_n_needed']}, comparator n ≈ {h['comparator_n_needed']})")
        L.append("")
    L += ["## Parameter provenance (who chose each rule)", "",
          "| Parameter | Value | Set by | Role | Process | Source |", "|---|---|---|---|---|---|"]
    for p in rep["parameters"]:
        L.append(f"| {p['name']} | {p['value']} | {p['set_by']} | {p['role']} | {p['process']} | {p.get('source') or '—'} |")
    if rep["warnings"]:
        L += ["", "## Warnings", ""] + [f"- `{w['code']}` {w['message']}" for w in rep["warnings"]]
    L += ["", "## Reproducibility", "",
          f"Software {rep['software']['name']} {rep['software']['version']} (commit {rep['software']['commit'] or 'n/a'}); "
          f"input sha256 `{rep['input_sha256'][:16]}…`; parameters sha256 `{rep['parameters_sha256'][:16]}…`. "
          f"Interval method: {rep['interval_citation']}. Zero handling: {rep['zero_handling']}.", "",
          "*This report describes statistical evidence relative to declared parameters. It makes no legal determination.*", ""]
    return "\n".join(L)


def _inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


def markdown_to_html(md: str, title: str = "libra-check report") -> str:
    out, i, lines = [], 0, md.split("\n")
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            out.append("<table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in rows[0]) + "</tr></thead><tbody>")
            for r in rows[2:]:
                out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>")
            out.append("</tbody></table>")
            continue
        if ln.startswith("# "):
            out.append(f"<h1>{_inline(ln[2:])}</h1>")
        elif ln.startswith("## "):
            out.append(f"<h2>{_inline(ln[3:])}</h2>")
        elif ln.startswith("> "):
            out.append(f"<p class='banner'>{_inline(ln[2:])}</p>")
        elif ln.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(f"<li>{_inline(lines[i][2:])}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif ln.strip():
            out.append(f"<p>{_inline(ln)}</p>")
        i += 1
    css = ("body{font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#1b1b1b;background:#fff}"
           "table{border-collapse:collapse;margin:8px 0;font-size:13px;display:block;overflow-x:auto}"
           "td,th{border:1px solid #ccc;padding:4px 8px;text-align:left}th{background:#f2f2f2}"
           ".banner{background:#fff3cd;padding:8px;border:1px solid #e0c060}code{background:#f4f4f4;padding:0 3px}"
           "@media (prefers-color-scheme: dark){body{background:#151515;color:#e6e6e6}th{background:#2a2a2a}"
           "td,th{border-color:#444}code{background:#2a2a2a}.banner{background:#4a3c10;border-color:#8a7020}}")
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
            f"content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title><style>{css}</style>"
            f"</head><body>{''.join(out)}</body></html>")


def to_html(rep: dict) -> str:
    return markdown_to_html(to_markdown(rep), title=f"Impact-ratio report {rep['report_id']}")
