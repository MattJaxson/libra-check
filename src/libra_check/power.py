"""Precision statements: what these sample sizes can and cannot resolve.

additional_n_hint   LARS R11: the scale factor on BOTH groups' n (rates held at their point
                    estimates) at which the interval would exclude theta. A precision
                    statement, not a prediction.
prob_states         P(determinate_below), P(determinate_at_or_above) for given true rates;
                    exact enumeration for moderate n, Monte Carlo with the actual interval method otherwise.
indeterminacy_band  at the observed n and comparator rate: the largest true IR that would be
                    flagged determinate_below with probability >= power, and the smallest true IR
                    that would be certified determinate_at_or_above with probability >= power.
                    True IRs strictly between the two are likely to come out indeterminate.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from .intervals import METHODS

EXACT_MAX_N1 = 1000
EXACT_MAX_N2 = 20000
TAIL = 1e-9


def _state(lo, hi, theta):
    if hi < theta:
        return "determinate_below"
    if lo >= theta:
        return "determinate_at_or_above"
    return "indeterminate"


def additional_n_hint(k1, n1, k2, n2, theta, z, method="mover_wilson", max_scale=1e6):
    """Smallest c >= 1 such that the interval at counts (c k1, c n1, c k2, c n2) excludes theta."""
    f = METHODS[method]
    if k2 <= 0 or n1 <= 0 or n2 <= 0:
        return None
    point = (k1 / n1) / (k2 / n2)
    if abs(point - theta) < 1e-12:
        return {"scale_factor": None, "note": "point estimate equals theta; no sample size resolves it"}

    def det(c):
        lo, hi = f(c * k1, c * n1, c * k2, c * n2, z=z)
        return _state(float(lo), float(hi), theta) != "indeterminate"

    if det(1.0):
        return {"scale_factor": 1.0, "focal_n_needed": int(n1), "comparator_n_needed": int(n2),
                "note": "already determinate"}
    a, b = 0.0, math.log(max_scale)
    if not det(max_scale):
        return {"scale_factor": None, "note": f"not resolvable below {max_scale:g}x the current sample"}
    for _ in range(60):
        m = 0.5 * (a + b)
        if det(math.exp(m)):
            b = m
        else:
            a = m
    c = math.exp(b)
    return {"scale_factor": round(c, 3), "focal_n_needed": int(math.ceil(c * n1)),
            "comparator_n_needed": int(math.ceil(c * n2)),
            "note": "if both point rates held; a precision statement, not a prediction"}


class _Exact:
    """Pre-computes the state of every (k1, k2) outcome, then probabilities are matrix products."""

    def __init__(self, n1, n2, p2, theta, z, method):
        self.n1, self.n2 = int(n1), int(n2)
        self.k1 = np.arange(self.n1 + 1)
        lo2 = int(stats.binom.ppf(TAIL, self.n2, p2)); hi2 = int(stats.binom.isf(TAIL, self.n2, p2))
        self.k2 = np.arange(max(lo2 - 1, 0), min(hi2 + 1, self.n2) + 1)
        self.w2 = stats.binom.pmf(self.k2, self.n2, p2)
        K1, K2 = np.meshgrid(self.k1, self.k2, indexing="ij")
        lo, hi = METHODS[method](K1, self.n1, K2, self.n2, z=z)
        self.below = (hi < theta).astype(float)
        self.above = (lo >= theta).astype(float)
        self.p2 = p2

    def probs(self, ir):
        p1 = min(ir * self.p2, 1.0)
        w1 = stats.binom.pmf(self.k1, self.n1, p1)
        return float(w1 @ self.below @ self.w2), float(w1 @ self.above @ self.w2)


def _approx_probs(n1, n2, p1, p2, theta, z):
    if p1 <= 0 or p1 >= 1:
        p1 = min(max(p1, 1e-12), 1 - 1e-12)
    se = math.sqrt((1 - p1) / (n1 * p1) + (1 - p2) / (n2 * p2))
    d = (math.log(p1 / p2) - math.log(theta)) / se
    return float(stats.norm.cdf(-d - z)), float(stats.norm.cdf(d - z))


MC_REPS = 4000
MC_SEED = 20261013


class _MonteCarlo:
    """Simulation with the ACTUAL interval method (common random numbers across true IRs)."""

    def __init__(self, n1, n2, p2, theta, z, method, reps=MC_REPS, seed=MC_SEED):
        rng = np.random.default_rng(seed)
        self.n1, self.n2, self.p2, self.theta, self.z, self.f = int(n1), int(n2), p2, theta, z, METHODS[method]
        self.k2 = rng.binomial(self.n2, p2, reps).astype(float)
        self.u = rng.random(reps)

    def probs(self, ir):
        p1 = min(ir * self.p2, 1.0)
        k1 = stats.binom.ppf(self.u, self.n1, p1)          # inverse-CDF draws: common random numbers
        lo, hi = self.f(k1, self.n1, self.k2, self.n2, z=self.z)
        return float(np.mean(hi < self.theta)), float(np.mean(lo >= self.theta))


def prob_states(n1, n2, p1, p2, theta, z, method="mover_wilson"):
    if n1 <= EXACT_MAX_N1 and n2 <= EXACT_MAX_N2:
        return _Exact(n1, n2, p2, theta, z, method).probs(p1 / p2), "exact_enumeration"
    return _MonteCarlo(n1, n2, p2, theta, z, method).probs(p1 / p2), f"monte_carlo_{MC_REPS}"


def indeterminacy_band(n1, n2, p2, theta, z, method="mover_wilson", power=0.80, step=0.005):
    if not (0 < p2 <= 1) or n1 < 1 or n2 < 1:
        return None
    ir_max = min(1.0 / p2, 3.0)
    grid = np.arange(step, ir_max + 1e-12, step)
    if n1 <= EXACT_MAX_N1 and n2 <= EXACT_MAX_N2:
        ex = _Exact(n1, n2, p2, theta, z, method)
        pr = np.array([ex.probs(g) for g in grid]); how = "exact_enumeration"
    else:
        mc = _MonteCarlo(n1, n2, p2, theta, z, method)
        grid = np.arange(0.01, ir_max + 1e-12, 0.01); step = 0.01
        pr = np.array([mc.probs(g) for g in grid]); how = f"monte_carlo_{MC_REPS}_actual_method"
    below_ok = grid[pr[:, 0] >= power]
    above_ok = grid[pr[:, 1] >= power]
    flag = float(below_ok.max()) if len(below_ok) else None
    cert = float(above_ok.min()) if len(above_ok) else None
    return {"power": power, "assumed_comparator_rate": round(float(p2), 6), "method": how, "grid_step": step,
            "flags_below_if_true_ir_at_most": None if flag is None else round(flag, 3),
            "certifies_at_or_above_if_true_ir_at_least": None if cert is None else round(cert, 3),
            "note": "true IRs between these values are likely (prob > 1 - power) to be classified indeterminate"}
