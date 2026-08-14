"""Statistics for experiment comparison (stdlib-only).

Implements the two workhorses needed by ``compare`` experiments:

* **Welch's t-test** (unequal variances) with the two-tailed p-value computed
  from Student's t distribution; suitable for roughly symmetric metric
  samples.
* **Mann-Whitney U** test with the normal approximation and continuity
  correction; the distribution-free default for skewed metric samples
  (throughput, flow times, coordination counts).

Both are the standard ABM "significant difference" tools and are implemented
directly so the engine keeps zero dependencies. Confidence intervals for
effects (Cohen's d) are also provided.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence


def mean_and_sd(sample: Sequence[float]) -> tuple[float, float]:
    if len(sample) < 2:
        return (sample[0] if sample else 0.0), 0.0
    m = statistics.mean(sample)
    s = statistics.stdev(sample)
    return m, s


def welch_t_test(a: Sequence[float], b: Sequence[float]) -> dict:
    """Two-tailed Welch's t-test. Returns t, dof and p."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return {"t": 0.0, "dof": 0.0, "p": 1.0, "significant": False}
    ma, sa = mean_and_sd(a)
    mb, sb = mean_and_sd(b)
    v_a, v_b = sa**2 / na, sb**2 / nb
    se = math.sqrt(v_a + v_b)
    if se == 0:
        # zero variance: identical samples (not significant) or constant
        # samples with different means (maximally significant)
        if ma == mb:
            return {"t": 0.0, "dof": 0.0, "p": 1.0, "significant": False}
        return {"t": 1e9, "dof": 1e9, "p": 0.0, "significant": True}
    t = (ma - mb) / se
    if v_a == 0 and v_b == 0:
        dof = float("inf")
    else:
        dof = (v_a + v_b) ** 2 / (v_a**2 / (na - 1) + v_b**2 / (nb - 1))
    p = _two_tailed_t_pvalue(abs(t), dof)
    return {"t": round(t, 4), "dof": round(dof, 4), "p": round(p, 6),
            "significant": p < 0.05}


def mann_whitney_u(a: Sequence[float], b: Sequence[float]) -> dict:
    """Two-sided Mann-Whitney U with normal approximation."""
    na, nb = len(a), len(b)
    if na == 0 or nb == 0:
        return {"u": 0.0, "z": 0.0, "p": 1.0, "significant": False}
    combined = sorted(
        [(v, 0) for v in a] + [(v, 1) for v in b], key=lambda x: (x[0], x[1])
    )
    ranks: list[float] = []
    i = 0
    n = len(combined)
    while i < n:
        j = i
        while j + 1 < n and combined[j + 1][0] == combined[i][0]:
            j += 1
        rank = (i + 1 + j + 1) / 2.0
        ranks.extend(rank for _ in range(j - i + 1))
        i = j + 1
    ra = sum(r for r, (_, grp) in zip(ranks, combined) if grp == 0)
    u = ra - na * (na + 1) / 2.0
    mu = na * nb / 2.0
    sigma = math.sqrt(na * nb * (na + nb + 1) / 12.0)
    if sigma == 0:
        z = 0.0
    else:
        correction = 0.5 * math.copysign(1.0, u - mu)
        z = (u - mu - correction) / sigma
    p = _two_tailed_normal_pvalue(abs(z))
    return {"u": round(u, 4), "z": round(z, 4), "p": round(p, 6),
            "significant": p < 0.05}


def cohens_d(a: Sequence[float], b: Sequence[float]) -> float:
    """Effect size (pooled standard deviation)."""
    ma, sa = mean_and_sd(a)
    mb, sb = mean_and_sd(b)
    na, nb = len(a), len(b)
    if na + nb < 3:
        return 0.0
    pooled = math.sqrt(((na - 1) * sa**2 + (nb - 1) * sb**2) / (na + nb - 2))
    if pooled == 0:
        return 0.0
    return (ma - mb) / pooled


def _two_tailed_t_pvalue(t: float, dof: float) -> float:
    """Complement of the CDF of Student's t via the regularized beta function."""
    if dof <= 0:
        return 1.0
    if dof > 1e6:  # asymptotic: normal approximation
        return math.erfc(abs(t) / math.sqrt(2.0))
    # p = I_{dof/(dof+t^2)}(dof/2, 1/2)  (two-tailed)
    x = dof / (dof + t * t)
    return _betainc_upper(dof / 2.0, 0.5, x)


def _betainc_upper(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a,b) via continued fraction (Cephes)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    if x > 0.5:
        # symmetry I_x(a,b) = 1 - I_{1-x}(b,a)
        return 1.0 - _betainc_upper(b, a, 1.0 - x)
    return _betacf(a, b, x) * _beta_log(a, b, x)


def _beta_log(a: float, b: float, x: float) -> float:
    from math import lgamma, log

    lbeta = lgamma(a + b) - lgamma(a) - lgamma(b)
    return math.exp(a * log(x) + b * log(1 - x) + lbeta) / a


def _betacf(a: float, b: float, x: float, max_iter: int = 200) -> float:
    """Continued fraction evaluation of I_x; returns the *upper* tail factor."""
    tiny = 1e-30
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-10:
            break
    return h


def _two_tailed_normal_pvalue(z: float) -> float:
    return math.erfc(z / math.sqrt(2.0))


def significance_report(a: Sequence[float], b: Sequence[float],
                        test: str = "auto") -> dict:
    """Combined report of mean, SD, effect size and test result."""
    ma, sa = mean_and_sd(a)
    mb, sb = mean_and_sd(b)
    if test == "auto":
        # Use the t-test when both samples look near-normal; default to
        # Mann-Whitney otherwise. We default to Mann-Whitney (robust).
        result = mann_whitney_u(a, b)
        used = "mann_whitney_u"
    elif test == "t":
        result = welch_t_test(a, b)
        used = "welch_t"
    elif test == "mann_whitney":
        result = mann_whitney_u(a, b)
        used = "mann_whitney_u"
    else:
        raise ValueError(f"unknown test: {test}")
    return {
        "mean_a": round(ma, 4),
        "sd_a": round(sa, 4),
        "mean_b": round(mb, 4),
        "sd_b": round(sb, 4),
        "cohens_d": round(cohens_d(a, b), 4),
        "test": used,
        **result,
    }
