"""Statistics used in the pre-registered analysis. Wilson interval follows post-cutoff-api-bench (same author)."""

from __future__ import annotations

import math
import random

Z = 1.959964


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + Z * Z / n
    centre = (p + Z * Z / (2 * n)) / den
    half = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def mcnemar_exact(b: int, c: int, alternative: str = "two-sided") -> float:
    """Exact McNemar on discordant pairs. b = pairs where only the first condition passed, c = only the second.
    alternative: 'two-sided', 'greater' (first passes more often), 'less' (first passes less often)."""
    n = b + c
    if n == 0:
        return 1.0

    def cdf(k: int) -> float:  # P(X <= k), X ~ Binomial(n, 1/2)
        return sum(math.comb(n, j) for j in range(0, k + 1)) / 2 ** n

    if alternative == "greater":
        return 1.0 - cdf(b - 1)
    if alternative == "less":
        return cdf(b)
    return min(1.0, 2 * cdf(min(b, c)))


def holm(pvalues: dict[str, float]) -> dict[str, float]:
    """Holm-adjusted p-values (step-down, monotone)."""
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    out, running = {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out


def cluster_bootstrap_diff(pairs_by_task: dict[str, list[tuple[int, int]]], iters: int = 10_000, seed: int = 0) -> tuple[float, float, float]:
    """Mean paired difference (first - second) with a 95% percentile interval, resampling tasks."""
    tasks = sorted(pairs_by_task)
    if not tasks:
        return (float("nan"),) * 3

    def mean_diff(sample):
        diffs = [a - b for t in sample for a, b in pairs_by_task[t]]
        return sum(diffs) / len(diffs) if diffs else 0.0

    rng = random.Random(seed)
    point = mean_diff(tasks)
    boots = sorted(mean_diff([rng.choice(tasks) for _ in tasks]) for _ in range(iters))
    return point, boots[int(0.025 * iters)], boots[int(0.975 * iters) - 1]
