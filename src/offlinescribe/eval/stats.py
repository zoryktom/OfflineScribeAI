"""Paired tests and interval estimates for ablation rows."""

from __future__ import annotations

from math import erf, sqrt


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def bootstrap_ci(
    values: list[float],
    n: int = 10_000,
    alpha: float = 0.05,
    *,
    n_boot: int | None = None,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Percentile bootstrap. Returns mean, lo, hi. Deterministic given seed."""
    draws = n_boot if n_boot is not None else n
    if not values:
        return 0.0, 0.0, 0.0
    center = mean(values)
    rng = _lcg(seed)
    samples: list[float] = []
    size = len(values)
    for _ in range(draws):
        draw = [values[next(rng) % size] for _ in range(size)]
        samples.append(mean(draw))
    samples.sort()
    lo_i = int((alpha / 2) * (draws - 1))
    hi_i = int((1 - alpha / 2) * (draws - 1))
    return center, samples[lo_i], samples[hi_i]


def mcnemar_paired(a: list[bool], b: list[bool]) -> tuple[float, float]:
    """McNemar chi-square and two-sided normal p-value on paired binaries."""
    if len(a) != len(b) or not a:
        raise ValueError("Paired lists required.")
    b01 = sum(1 for x, y in zip(a, b) if (not x) and y)
    b10 = sum(1 for x, y in zip(a, b) if x and (not y))
    disc = b01 + b10
    if disc == 0:
        return 0.0, 1.0
    chi = (abs(b01 - b10) - 1) ** 2 / disc
    # chi-square 1 df survival via erfc-like normal of sqrt(chi)
    z = sqrt(max(chi, 0.0))
    p = 2 * (1 - _phi(z))
    return chi, min(1.0, max(0.0, p))


def wilcoxon_paired(a: list[float], b: list[float]) -> tuple[float, float]:
    """Sign-test z and approximate two-sided p. SciPy not required."""
    signed = wilcoxon_signed_pairs(a, b)
    z = float(signed["z_approx"])
    p = 2 * (1 - _phi(abs(z)))
    return z, min(1.0, max(0.0, p))


def wilcoxon_signed_pairs(a: list[float], b: list[float]) -> dict[str, float]:
    if len(a) != len(b) or not a:
        raise ValueError("Paired lists required.")
    plus = sum(1 for x, y in zip(a, b) if x > y)
    minus = sum(1 for x, y in zip(a, b) if x < y)
    ties = len(a) - plus - minus
    n = plus + minus
    if n == 0:
        z = 0.0
    else:
        z = (plus - n / 2) / sqrt(n / 4)
    return {"plus": plus, "minus": minus, "ties": ties, "z_approx": z}


def mixed_effects(df: list[dict], formula: str, groups: str) -> dict:
    """Requires statsmodels. Not run in default CI."""
    raise NotImplementedError(
        f"Install statsmodels to fit {formula!r} with groups={groups!r}. n={len(df)}"
    )


def holm_bonferroni(pvals: list[float]) -> list[float]:
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, idx in enumerate(order):
        adj = (m - rank) * pvals[idx]
        running = max(running, adj)
        adjusted[idx] = min(1.0, running)
    return adjusted


def _phi(z: float) -> float:
    return 0.5 * (1 + erf(z / sqrt(2)))


def _lcg(seed: int):
    state = seed & 0xFFFFFFFF
    while True:
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        yield state
