# Copied (unmodified except this header and the helpers appended at the end) from
# analysis/ci_methods.py of the paper-reproduction repository (ll144-indeterminacy), sha256 7451da441d9342479f0c9aab3893e4fd5b364a715bdee1adae1e74d3ae534028, on 2026-10-13.
"""Confidence intervals for the ratio of two independent binomial proportions (v1).

IR = p1 / p2 where group 1 is the focal group (x1 of n1 selected) and group 2 the
reference group (x2 of n2). All functions are vectorized over numpy arrays and take
`z`, the standard-normal quantile for ONE tail: z = 1.6449 gives one-sided 95% bounds
(equivalently a two-sided 90% interval), z = 1.9600 one-sided 97.5% / two-sided 95%.

Methods
  wilson_bounds   Wilson score interval for one proportion.
  mover_wilson    MOVER-R with Wilson limits (Donner & Zou 2012, ratio-scale form; also
                  Newcombe 2013, Fagerland et al. 2015). Closed form, handles zero cells.
  score_ratio     Asymptotic score interval obtained by inverting the score statistic with
                  the restricted MLE of Miettinen & Nurminen (1985) / Farrington & Manning (1990).
                  correction=False -> Koopman (1984) asymptotic score interval;
                  correction=True  -> Miettinen-Nurminen (variance x N/(N-1)).
                  Verified against statsmodels.confint_proportions_2indep(compare="ratio",
                  method="score") in tests (see verify_against_statsmodels()).
  katz_log        Katz log interval, 0.5 added to every cell when any cell is zero.
  bootstrap_pct   Parametric percentile bootstrap (secondary; shown to fail at small counts).
"""
from __future__ import annotations

import numpy as np
from scipy import stats

Z90 = float(stats.norm.ppf(0.95))    # one-sided 5% per side (two-sided 90%) -- PRIMARY
Z95 = float(stats.norm.ppf(0.975))   # one-sided 2.5% per side (two-sided 95%) -- sensitivity


def _arr(*xs):
    return [np.asarray(x, dtype=float) for x in xs]


# ------------------------------------------------------------------ one proportion
def wilson_bounds(x, n, z=Z90):
    x, n = _arr(x, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = x / n
        denom = 1 + z**2 / n
        centre = (p + z**2 / (2 * n)) / denom
        half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    lo = np.clip(centre - half, 0.0, 1.0)
    hi = np.clip(centre + half, 0.0, 1.0)
    lo = np.where(x <= 0, 0.0, lo)
    hi = np.where(x >= n, 1.0, hi)
    return lo, hi


# ------------------------------------------------------------------ MOVER-R Wilson
def mover_wilson(x1, n1, x2, n2, z=Z90):
    """MOVER-R for p1/p2 (Donner & Zou 2012, eq. for ratios) using Wilson limits.
    L = [p1 p2 - sqrt((p1 p2)^2 - l1 u2 (2p1 - l1)(2p2 - u2))] / [u2 (2p2 - u2)]
    U = [p1 p2 + sqrt((p1 p2)^2 - u1 l2 (2p1 - u1)(2p2 - l2))] / [l2 (2p2 - l2)]
    """
    x1, n1, x2, n2 = _arr(x1, n1, x2, n2)
    p1, p2 = x1 / n1, x2 / n2
    l1, u1 = wilson_bounds(x1, n1, z)
    l2, u2 = wilson_bounds(x2, n2, z)
    a = p1 * p2
    with np.errstate(divide="ignore", invalid="ignore"):
        dl = u2 * (2 * p2 - u2)
        du = l2 * (2 * p2 - l2)
        lo = (a - np.sqrt(np.maximum(a**2 - l1 * u2 * (2 * p1 - l1) * (2 * p2 - u2), 0))) / dl
        hi = (a + np.sqrt(np.maximum(a**2 - u1 * l2 * (2 * p1 - u1) * (2 * p2 - l2), 0))) / du
    # Denominators of the MOVER-R formula vanish/turn negative only in degenerate cells:
    # x2 = 0 -> reference rate 0, ratio unbounded above; lower limit 0.
    lo = np.where(x1 <= 0, 0.0, lo)
    lo = np.where((dl <= 0) | ~np.isfinite(lo), 0.0, lo)
    hi = np.where((x2 <= 0) | (du <= 0) | ~np.isfinite(hi), np.inf, hi)
    return np.maximum(lo, 0.0), hi


# ------------------------------------------------------------------ score (Koopman / MN)
def _restricted_mle(x1, n1, x2, n2, theta):
    """Restricted MLE of (p1, p2) under p1 = theta * p2 (Miettinen & Nurminen 1985)."""
    N = n1 + n2
    A = N * theta
    B = -(n1 * theta + x1 + n2 + x2 * theta)
    C = x1 + x2
    disc = np.maximum(B * B - 4 * A * C, 0.0)
    p2 = (-B - np.sqrt(disc)) / (2 * A)
    p2 = np.clip(p2, 0.0, 1.0)
    p1 = np.clip(theta * p2, 0.0, 1.0)
    return p1, p2


def score_stat(x1, n1, x2, n2, theta, correction=False):
    """Signed score statistic for H0: p1/p2 = theta. Decreasing in theta."""
    p1t, p2t = _restricted_mle(x1, n1, x2, n2, theta)
    var = p1t * (1 - p1t) / n1 + theta**2 * p2t * (1 - p2t) / n2
    if correction:
        N = n1 + n2
        var = var * N / (N - 1)
    num = x1 / n1 - theta * x2 / n2
    with np.errstate(divide="ignore", invalid="ignore"):
        s = num / np.sqrt(var)
        # var == 0 only when the restricted MLE is degenerate; the sign of the numerator decides
        s = np.where(var > 0, s, np.sign(num) * np.inf)
    s = np.where(num == 0, 0.0, s)
    return s


def score_ratio(x1, n1, x2, n2, z=Z90, correction=False, iters=80, lo_t=1e-8, hi_t=1e8):
    """Invert the score test by bisection on log(theta). Returns (lower, upper)."""
    x1, n1, x2, n2 = np.broadcast_arrays(*_arr(x1, n1, x2, n2))

    def root(target):
        # find theta with score_stat(theta) = target; score_stat is decreasing in theta
        a = np.full(x1.shape, np.log(lo_t))
        b = np.full(x1.shape, np.log(hi_t))
        for _ in range(iters):
            m = 0.5 * (a + b)
            s = score_stat(x1, n1, x2, n2, np.exp(m), correction)
            go_right = s > target
            a = np.where(go_right, m, a)
            b = np.where(go_right, b, m)
        return np.exp(0.5 * (a + b))

    lo = root(z)
    hi = root(-z)
    # boundary cases: if even theta -> 0 cannot reach +z, lower limit is 0 (x1 = 0);
    # if theta -> inf cannot reach -z, the upper limit is infinite (x2 = 0).
    s_lo = score_stat(x1, n1, x2, n2, np.full(x1.shape, lo_t), correction)
    s_hi = score_stat(x1, n1, x2, n2, np.full(x1.shape, hi_t), correction)
    lo = np.where((x1 <= 0) | (s_lo <= z), 0.0, lo)
    hi = np.where((x2 <= 0) | (s_hi >= -z), np.inf, hi)
    return lo, hi


def koopman(x1, n1, x2, n2, z=Z90):
    return score_ratio(x1, n1, x2, n2, z, correction=False)


def miettinen_nurminen(x1, n1, x2, n2, z=Z90):
    return score_ratio(x1, n1, x2, n2, z, correction=True)


# ------------------------------------------------------------------ Katz log
def katz_log(x1, n1, x2, n2, z=Z90):
    x1, n1, x2, n2 = np.broadcast_arrays(*_arr(x1, n1, x2, n2))
    zero = (x1 == 0) | (x2 == 0) | (x1 == n1) | (x2 == n2)
    a1 = np.where(zero, x1 + 0.5, x1); m1 = np.where(zero, n1 + 1, n1)
    a2 = np.where(zero, x2 + 0.5, x2); m2 = np.where(zero, n2 + 1, n2)
    r = (a1 / m1) / (a2 / m2)
    se = np.sqrt(1 / a1 - 1 / m1 + 1 / a2 - 1 / m2)
    lo, hi = r * np.exp(-z * se), r * np.exp(z * se)
    # libra-check fix (validation BUG-1, 2026-10-13): the +0.5 correction can push the whole interval above the
    # point estimate when x1 = 0; apply the documented zero handling (focal 0 -> lower 0; comparator 0 -> upper inf).
    lo = np.where(x1 <= 0, 0.0, lo)
    hi = np.where(x2 <= 0, np.inf, hi)
    return lo, hi


# ------------------------------------------------------------------ bootstrap
def bootstrap_pct(x1, n1, x2, n2, rng, z=Z90, reps=2000):
    """Parametric percentile bootstrap for scalar inputs. Resamples with ratio undefined
    (reference count 0) are dropped; if the observed reference count is 0, returns (0, inf)."""
    if x2 == 0:
        return 0.0, np.inf
    q = stats.norm.cdf(-z)
    b1 = rng.binomial(int(n1), x1 / n1, reps) / n1
    b2 = rng.binomial(int(n2), x2 / n2, reps) / n2
    ok = b2 > 0
    lo, hi = np.quantile(b1[ok] / b2[ok], [q, 1 - q])
    return float(lo), float(hi)


METHODS = {
    "mover_wilson": mover_wilson,
    "koopman": koopman,
    "miettinen_nurminen": miettinen_nurminen,
    "katz_log": katz_log,
}
PRIMARY = "mover_wilson"
LABELS = {"mover_wilson": "MOVER-R Wilson", "koopman": "Koopman score",
          "miettinen_nurminen": "Miettinen--Nurminen score", "katz_log": "Katz log",
          "bootstrap": "Percentile bootstrap"}


# ------------------------------------------------------------------ decision rule
BELOW, INDET, ATABOVE = "below", "indeterminate", "at_or_above"


def classify(lo, hi, theta):
    """Three-outcome decision rule.
    BELOW    : upper bound < theta  (one-sided test rejects IR >= theta)
    ATABOVE  : lower bound >= theta (non-inferiority with margin theta: rejects IR < theta)
    INDET    : neither."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    out = np.full(lo.shape, INDET, dtype=object)
    out[hi < theta] = BELOW
    out[lo >= theta] = ATABOVE
    return out



# ------------------------------------------------------------------ libra-check additions
from scipy import stats as _stats  # noqa: E402

CITATIONS = {
    "mover_wilson": "MOVER-R with Wilson limits: Donner & Zou (2012) Stat Methods Med Res 21(4):347-359, "
                    "doi:10.1177/0962280210383082; Newcombe (2016) Stat Methods Med Res 25(5):1774-1778, "
                    "doi:10.1177/0962280213502144; Wilson (1927) JASA 22:209-212, doi:10.1080/01621459.1927.10502953",
    "koopman": "Koopman PAR (1984). Confidence intervals for the ratio of two binomial proportions. Biometrics 40(2):513-517, doi:10.2307/2531405",
    "miettinen_nurminen": "Miettinen O, Nurminen M (1985). Comparative analysis of two rates. Stat Med 4(2):213-226, doi:10.1002/sim.4780040211",
    "katz_log": "Katz D, Baptista J, Azen SP, Pike MC (1978). Obtaining confidence intervals for the risk ratio in "
                "cohort studies. Biometrics 34(3):469-474, doi:10.2307/2530610",
}
ZERO_HANDLING = {
    "mover_wilson": "closed form; Wilson limits are defined at k=0 and k=n; focal k=0 gives lower=0; "
                    "comparator k=0 makes the ratio not estimable",
    "koopman": "score inversion; focal k=0 gives lower=0; comparator k=0 gives upper=inf (not estimable)",
    "miettinen_nurminen": "score inversion with N/(N-1) variance factor; zero handling as Koopman",
    "katz_log": "0.5 added to every cell when any cell is 0 or equals n",
}


def z_for(alpha_two_sided: float, m: int = 1) -> float:
    """Normal quantile giving one-sided error alpha_two_sided/2 per bound, Bonferroni-split over m."""
    return float(_stats.norm.ppf(1 - alpha_two_sided / (2 * m)))
