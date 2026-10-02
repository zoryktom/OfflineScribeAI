"""Small-sample statistics for paired ablation rows. Not a clinical trial analysis."""

from __future__ import annotations

from math import sqrt


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def bootstrap_ci(values: list[float], *, n_boot: int = 400, seed: int = 0) -> tuple[float, float, float]:
    """Percentile bootstrap CI. Deterministic given seed."""
    if not values:
        return 0.0, 0.0, 0.0
    center = mean(values)
    rng = _lcg(seed)
    samples: list[float] = []
    n = len(values)
    for _ in range(n_boot):
        draw = [values[next(rng) % n] for _ in range(n)]
        samples.append(mean(draw))
    samples.sort()
    lo = samples[int(0.025 * (n_boot - 1))]
    hi = samples[int(0.975 * (n_boot - 1))]
    return center, lo, hi


def wilcoxon_signed_pairs(a: list[float], b: list[float]) -> dict[str, float]:
    """Sign-test stand-in when SciPy is absent. Reports win counts, not a p-value claim."""
    if len(a) != len(b) or not a:
        raise ValueError("Paired lists required.")
    plus = sum(1 for x, y in zip(a, b) if x > y)
    minus = sum(1 for x, y in zip(a, b) if x < y)
    ties = len(a) - plus - minus
    n = plus + minus
    # Two-sided binomial normal approximation; documented as approximate.
    if n == 0:
        z = 0.0
    else:
        z = (plus - n / 2) / sqrt(n / 4)
    return {"plus": plus, "minus": minus, "ties": ties, "z_approx": z}


def holm_bonferroni(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values. Input must already be p-values."""
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, idx in enumerate(order):
        adj = (m - rank) * p_values[idx]
        running = max(running, adj)
        adjusted[idx] = min(1.0, running)
    return adjusted


def _lcg(seed: int):
    state = seed & 0xFFFFFFFF
    while True:
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        yield state
