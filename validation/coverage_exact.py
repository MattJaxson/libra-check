"""Exact-enumeration coverage of every interval method shipped in libra-check, plus the error
rate of libra-check's three-state DECISION at the 0.80 boundary.

Approach follows analysis/coverage.py in the paper-reproduction repository (ll144-indeterminacy; read, not imported): for each design
(n_focal, n_ref = r * n_focal, p_ref, true IR) enumerate every outcome (k1, k2) with its
binomial probability, evaluate the interval, and sum probabilities of
  lowtail  P(lower > IR)  -- would wrongly support a "determinate_at_or_above"-type claim
  uptail   P(upper < IR)  -- would wrongly support a "determinate_below"-type claim
Nominal per tail = alpha/2 (alpha = 0.10 -> 5%, alpha = 0.05 -> 2.5%), z = libra_check.intervals.z_for(alpha).
Binomial support is truncated at 1e-10 in each tail; the dropped mass is reported per design.

Decision error at theta = 0.80 (state rule copied from libra_check.core.state_of semantics:
below iff U < theta, at_or_above iff L >= theta):
  P(determinate_at_or_above | true IR = theta - delta)   (false clear)
  P(determinate_below       | true IR = theta + delta)   (false flag)
for delta in {0, 0.02, 0.05}.

Outputs (validation/out/):
  coverage_exact.csv          one row per design x alpha x method
  coverage_summary.json/.md   per method x alpha: max / median per-tail non-coverage, share of designs > nominal + 1 pp
  decision_boundary.csv/.md   decision error rates at the boundary (max / median over designs)
Run (from the libra-check directory, with libra-check and pandas installed): python validation/coverage_exact.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from libra_check.intervals import METHODS, z_for

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
TAIL = 1e-10
SEED = 20261013  # no randomness is used (exact enumeration); recorded for the run log only

N_FOCAL = (10, 20, 30, 50, 100, 200, 500, 1000)
RATIO = (1, 5, 20)
P_REF = (0.05, 0.10, 0.20, 0.30, 0.50)
TRUE_IR = (0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 1.00)
THETA = 0.80
DELTAS = (0.0, 0.02, 0.05)
ALPHAS = (0.10, 0.05)
EXTRA_IR = tuple(sorted({round(THETA - d, 4) for d in DELTAS} | {round(THETA + d, 4) for d in DELTAS}))
ALL_IR = tuple(sorted(set(TRUE_IR) | set(EXTRA_IR)))


def support(n, p):
    lo = int(stats.binom.ppf(TAIL, n, p))
    hi = int(stats.binom.isf(TAIL, n, p))
    k = np.arange(max(lo - 1, 0), min(hi + 1, n) + 1)
    return k, stats.binom.pmf(k, n, p)


def grid() -> pd.DataFrame:
    rows = []
    for n1 in N_FOCAL:
        for r in RATIO:
            n2 = r * n1
            for p2 in P_REF:
                k2, w2 = support(n2, p2)
                for ir in ALL_IR:
                    p1 = ir * p2
                    k1, w1 = support(n1, p1)
                    K1, K2 = np.meshgrid(k1, k2, indexing="ij")
                    W = np.outer(w1, w2)
                    dropped = float(1 - W.sum())
                    for alpha in ALPHAS:
                        z = z_for(alpha)
                        for m, fn in METHODS.items():
                            lo, hi = fn(K1, n1, K2, n2, z=z)
                            rows.append(dict(
                                n_focal=n1, ratio=r, n_ref=n2, p_ref=p2, true_ir=ir, alpha=alpha, method=m,
                                nominal_per_tail=alpha / 2,
                                lowtail=float(W[lo > ir].sum()), uptail=float(W[hi < ir].sum()),
                                p_state_at_or_above=float(W[lo >= THETA].sum()),
                                p_state_below=float(W[hi < THETA].sum()),
                                p_upper_infinite=float(W[~np.isfinite(hi)].sum()),
                                dropped_mass=dropped, cells=int(W.size)))
        print(f"  n_focal={n1} done", flush=True)
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    cov = df[df.true_ir.round(4).isin([round(x, 4) for x in TRUE_IR])]
    out = []
    for (alpha, m), g in cov.groupby(["alpha", "method"], sort=False):
        nom = alpha / 2
        for tail in ("lowtail", "uptail"):
            v = g[tail]
            d = dict(alpha=alpha, method=m, tail=tail, nominal=nom, n_designs=len(v),
                     max=float(v.max()), median=float(v.median()), mean=float(v.mean()),
                     share_gt_nominal_plus_1pp=float((v > nom + 0.01).mean()))
            for nf in (30, 100):
                d[f"max_nfocal_ge{nf}"] = float(v[g.n_focal >= nf].max())
                d[f"share_gt_nom_1pp_nfocal_ge{nf}"] = float((v[g.n_focal >= nf] > nom + 0.01).mean())
            worst = g.loc[v.idxmax()]
            d["worst_design"] = f"n1={worst.n_focal},n2={worst.n_ref},p_ref={worst.p_ref},IR={worst.true_ir}"
            out.append(d)
    return pd.DataFrame(out)


def decision(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for (alpha, m), g in df.groupby(["alpha", "method"], sort=False):
        for d in DELTAS:
            for kind, ir, col in (("false_at_or_above (IR=theta-delta)", round(THETA - d, 4), "p_state_at_or_above"),
                                  ("false_below (IR=theta+delta)", round(THETA + d, 4), "p_state_below")):
                v = g[g.true_ir.round(4) == ir][col]
                out.append(dict(alpha=alpha, nominal_per_bound=alpha / 2, method=m, delta=d, error=kind, true_ir=ir,
                                n_designs=len(v), max=float(v.max()), median=float(v.median()),
                                max_nfocal_ge30=float(v[g[g.true_ir.round(4) == ir].n_focal >= 30].max()),
                                share_gt_nominal_plus_1pp=float((v > alpha / 2 + 0.01).mean())))
    return pd.DataFrame(out)


def to_md(df: pd.DataFrame, cols, floatfmt="{:.4f}") -> str:
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df[cols].iterrows():
        lines.append("| " + " | ".join(floatfmt.format(x) if isinstance(x, float) else str(x) for x in r) + " |")
    return "\n".join(lines)


def main():
    t0 = time.time()
    df = grid()
    df.to_csv(OUT / "coverage_exact.csv", index=False)
    s = summarize(df)
    dec = decision(df)
    dec.to_csv(OUT / "decision_boundary.csv", index=False)
    meta = {"n_designs_coverage": int(len(df[df.true_ir.round(4).isin([round(x, 4) for x in TRUE_IR])]) // (len(ALPHAS) * len(METHODS))),
            "max_dropped_mass": float(df.dropped_mass.max()), "tail_truncation": TAIL,
            "z": {str(a): z_for(a) for a in ALPHAS}, "theta": THETA, "runtime_s": round(time.time() - t0, 1),
            "methods": list(METHODS), "libra_check_version": __import__("libra_check").__version__}
    (OUT / "coverage_summary.json").write_text(json.dumps({"meta": meta, "summary": s.to_dict(orient="records")}, indent=1))
    md = ["# Exact coverage of libra-check interval methods", "",
          f"Generated by `validation/coverage_exact.py`. Designs per (method, alpha): "
          f"{meta['n_designs_coverage']}; max dropped mass {meta['max_dropped_mass']:.2e}.", "",
          "## Per-tail non-coverage (lowtail = P(L > IR); uptail = P(U < IR))", "",
          to_md(s, ["alpha", "method", "tail", "nominal", "max", "median", "share_gt_nominal_plus_1pp",
                    "max_nfocal_ge30", "share_gt_nom_1pp_nfocal_ge30", "worst_design"]), "",
          "## Three-state decision error at theta = 0.80", "",
          to_md(dec, ["alpha", "method", "delta", "error", "nominal_per_bound", "max", "median", "max_nfocal_ge30",
                      "share_gt_nominal_plus_1pp"])]
    (OUT / "coverage_summary.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
