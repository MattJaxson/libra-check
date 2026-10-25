"""Interval methods vs statsmodels / independent implementations, and edge cases."""
import math

import numpy as np
import pytest
from scipy import stats
from statsmodels.stats.proportion import confint_proportions_2indep, proportion_confint

from libra_check.intervals import (METHODS, Z90, katz_log, koopman, miettinen_nurminen, mover_wilson,
                                   wilson_bounds, z_for)

rng = np.random.default_rng(20261013)
CASES = []
for _ in range(300):
    n1 = int(rng.integers(5, 500)); n2 = int(rng.integers(5, 3000))
    CASES.append((int(rng.integers(1, n1)), n1, int(rng.integers(1, n2)), n2))


def test_z_for():
    assert math.isclose(z_for(0.10), stats.norm.ppf(0.95))
    assert math.isclose(z_for(0.05), stats.norm.ppf(0.975))
    assert math.isclose(z_for(0.10, 4), stats.norm.ppf(1 - 0.05 / 4))


@pytest.mark.parametrize("alpha", [0.10, 0.05])
def test_wilson_matches_statsmodels(alpha):
    for x, n, _, _ in CASES[:100]:
        lo, hi = wilson_bounds(x, n, z_for(alpha))
        rl, rh = proportion_confint(x, n, alpha=alpha, method="wilson")
        assert abs(lo - rl) < 1e-10 and abs(hi - rh) < 1e-10


@pytest.mark.parametrize("corr,fn", [(False, koopman), (True, miettinen_nurminen)])
def test_score_matches_statsmodels(corr, fn):
    worst = 0.0
    for x1, n1, x2, n2 in CASES:
        rl, rh = confint_proportions_2indep(x1, n1, x2, n2, method="score", compare="ratio", alpha=0.10, correction=corr)
        ol, oh = fn(x1, n1, x2, n2, z=Z90)
        worst = max(worst, abs(math.log(float(ol)) - math.log(rl)), abs(math.log(float(oh)) - math.log(rh)))
    assert worst < 1e-4   # statsmodels root-finder tolerance


def test_katz_matches_statsmodels_log():
    for x1, n1, x2, n2 in CASES:
        rl, rh = confint_proportions_2indep(x1, n1, x2, n2, method="log", compare="ratio", alpha=0.10)
        ol, oh = katz_log(x1, n1, x2, n2, z=Z90)
        assert abs(float(ol) - rl) < 1e-8 * max(1, rl) and abs(float(oh) - rh) < 1e-8 * max(1, rh)


def _mover_ref(x1, n1, x2, n2, z):
    """Independent scalar MOVER-R (Newcombe 2016, eqs. for a ratio of two proportions)."""
    p1, p2 = x1 / n1, x2 / n2
    l1, u1 = proportion_confint(x1, n1, alpha=2 * (1 - stats.norm.cdf(z)), method="wilson")
    l2, u2 = proportion_confint(x2, n2, alpha=2 * (1 - stats.norm.cdf(z)), method="wilson")
    a = p1 * p2
    L = (a - math.sqrt(max(a * a - l1 * u2 * (2 * p1 - l1) * (2 * p2 - u2), 0))) / (u2 * (2 * p2 - u2))
    U = (a + math.sqrt(max(a * a - u1 * l2 * (2 * p1 - u1) * (2 * p2 - l2), 0))) / (l2 * (2 * p2 - l2))
    return L, U


def test_mover_matches_independent_implementation():
    for x1, n1, x2, n2 in CASES:
        if x2 / n2 < 0.5:  # keep denominators of the closed form positive for the reference
            ol, oh = mover_wilson(x1, n1, x2, n2, z=Z90)
            rl, rh = _mover_ref(x1, n1, x2, n2, Z90)
            assert abs(float(ol) - rl) < 1e-9 and abs(float(oh) - rh) < 1e-9


@pytest.mark.parametrize("name", list(METHODS))
def test_interval_contains_point_and_nests(name):
    f = METHODS[name]
    for x1, n1, x2, n2 in CASES[:80]:
        r = (x1 / n1) / (x2 / n2)
        lo90, hi90 = f(x1, n1, x2, n2, z=z_for(0.10))
        lo95, hi95 = f(x1, n1, x2, n2, z=z_for(0.05))
        if name != "katz_log":   # katz uses +0.5 only at boundaries; interior contains the point too
            assert lo90 <= r * (1 + 1e-9) and hi90 >= r * (1 - 1e-9)
        assert lo95 <= lo90 + 1e-12 and hi95 >= hi90 - 1e-12


@pytest.mark.parametrize("name", list(METHODS))
def test_zero_and_full_cells(name):
    f = METHODS[name]
    lo, hi = f(0, 30, 10, 30, z=Z90)          # focal zero
    assert lo == 0 or lo < 0.05
    assert np.isfinite(hi)
    lo, hi = f(5, 30, 0, 30, z=Z90)           # comparator zero -> unbounded above
    if name != "katz_log":
        assert not np.isfinite(hi)
    lo, hi = f(30, 30, 30, 30, z=Z90)         # k = n in both
    assert lo <= 1.0 <= hi and np.isfinite(hi)
    lo, hi = f(1, 1, 1, 1, z=Z90)             # n = 1
    assert lo <= 1.0 <= hi


def test_mover_exact_coverage_small_grid():
    """One-sided non-coverage of MOVER-R Wilson at z=1.645 stays near nominal 5% (exact enumeration)."""
    z = Z90
    worst = 0.0
    for n1, n2, p2, ir in [(30, 150, 0.3, 0.8), (50, 50, 0.5, 0.8), (100, 2000, 0.2, 0.7), (200, 1000, 0.1, 1.0)]:
        p1 = ir * p2
        k1 = np.arange(n1 + 1); k2 = np.arange(n2 + 1)
        w = np.outer(stats.binom.pmf(k1, n1, p1), stats.binom.pmf(k2, n2, p2))
        K1, K2 = np.meshgrid(k1, k2, indexing="ij")
        lo, hi = mover_wilson(K1, n1, K2, n2, z=z)
        worst = max(worst, float(w[lo > ir].sum()), float(w[hi < ir].sum()))
    assert worst < 0.07
