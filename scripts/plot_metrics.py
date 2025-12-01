#!/usr/bin/env python3
"""
Build bar charts comparing MOVNS vs NSGA-II across multiple seeds for a given time budget.

Reads Pareto sets from:
  - NSGA-II: results/run-<time>s-nsga-<k>/nsga2-pareto-set.csv
             nsga2/results/run-<time>s-nsga-<k>/nsga2-pareto-set.csv
             results/run-<time>s/nsga2-pareto-set.csv
             nsga2/results/run-<time>s/nsga2-pareto-set.csv
  - MOVNS:   movns-results/run-<time>s-movns-<k>/movns-pareto-set.csv
             movns-results/run-<time>s/movns-pareto-set.csv
             movns-results/run-<time>s-merged/movns-pareto-set.csv

Metrics: HV (dynamic ref point), IGD (ref = union), Spread, Pareto size, epsilon.
Saves: results/metrics_comparison_<time>s.png
"""

import argparse
import csv
import math
import os
from typing import List, Sequence

import matplotlib.pyplot as plt
import numpy as np

MAXIMIZE = [True, True, False, False]
PADDING = 1.05  # margin for HV ref point


def load_pareto(path: str) -> List[List[float]]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    pts = []
    for r in rows:
        try:
            pts.append([
                float(r["TotalAttractions"]),
                float(r["TotalQuality"]),
                float(r["TotalTime"]),
                float(r["TotalCost"]),
            ])
        except Exception:
            continue
    return pts


def compute_ref_point(points: Sequence[Sequence[float]]) -> List[float]:
    if not points:
        return [20.0, 100.0, 1500.0, 1000.0]
    ref = []
    for j in range(len(points[0])):
        mx = max(p[j] for p in points)
        ref.append(mx * PADDING if mx != 0 else 1.0)
    return ref


def normalize(points: Sequence[Sequence[float]], ref_point: Sequence[float]) -> List[List[float]]:
    norm = []
    for p in points:
        n = []
        for v, ref, is_max in zip(p, ref_point, MAXIMIZE):
            n.append((ref - v) / ref if is_max else v / ref if ref else 0.0)
        if all(0.0 <= x <= 1.0 for x in n):
            norm.append(n)
    return norm


def hypervolume(points: Sequence[Sequence[float]], ref_point: Sequence[float]) -> float:
    n = normalize(points, ref_point)
    if not n:
        return 0.0
    return sum(np.prod([1 - v for v in p]) for p in n) / len(n)


def spread(points: Sequence[Sequence[float]]) -> float:
    if len(points) < 2:
        return 1.0
    m = len(points[0]); total = 0.0
    for j in range(m):
        vals = sorted(p[j] for p in points)
        if len(vals) < 2:
            continue
        fmin, fmax = vals[0], vals[-1]
        if fmax == fmin:
            continue
        d = [vals[i+1] - vals[i] for i in range(len(vals)-1)]
        if not d:
            continue
        mean = sum(d)/len(d)
        if mean == 0:
            continue
        df = abs(vals[0] - fmin)
        dl = abs(vals[-1] - fmax)
        total += (df + dl + sum(abs(x-mean) for x in d)) / (df + dl + len(d)*mean)
    return total/m if m else 1.0


def epsilon(points1: Sequence[Sequence[float]], points2: Sequence[Sequence[float]]) -> float:
    """epsilon(points2 vs points1); lower is better for points2."""
    if not points1 or not points2:
        return float("inf")
    obj1 = np.array(points1, dtype=float)
    obj2 = np.array(points2, dtype=float)
    mins = np.min(np.vstack([obj1, obj2]), axis=0)
    maxs = np.max(np.vstack([obj1, obj2]), axis=0)
    rng = maxs - mins
    rng[rng == 0] = 1.0
    n1 = np.zeros_like(obj1); n2 = np.zeros_like(obj2)
    for i, is_max in enumerate(MAXIMIZE):
        if is_max:
            n1[:, i] = (obj1[:, i] - mins[i]) / rng[i]
            n2[:, i] = (obj2[:, i] - mins[i]) / rng[i]
        else:
            n1[:, i] = 1 - (obj1[:, i] - mins[i]) / rng[i]
            n2[:, i] = 1 - (obj2[:, i] - mins[i]) / rng[i]
    eps = []
    for s2 in n2:
        eps.append(min(np.max(s2 - s1) for s1 in n1))
    return max(eps) if eps else float("inf")


def igd(solutions: Sequence[Sequence[float]], reference: Sequence[Sequence[float]]) -> float:
    if not solutions or not reference:
        return float("inf")
    total = 0.0
    for ref_pt in reference:
        best = min(math.dist(ref_pt, sol) for sol in solutions)
        total += best
    return total / len(reference)


def pick_nsga(time_sec: int, k: int) -> str:
    candidates = [
        f"results/run-{time_sec}s-nsga-{k}/nsga2-pareto-set.csv",
        f"nsga2/results/run-{time_sec}s-nsga-{k}/nsga2-pareto-set.csv",
        f"results/run-{time_sec}s/nsga2-pareto-set.csv",
        f"nsga2/results/run-{time_sec}s/nsga2-pareto-set.csv",
    ]
    return next((p for p in candidates if os.path.exists(p)), "")


def pick_movns(time_sec: int, k: int) -> str:
    candidates = [
        f"movns-results/run-{time_sec}s-movns-{k}/movns-pareto-set.csv",
        f"movns-results/run-{time_sec}s/movns-pareto-set.csv",
        f"movns-results/run-{time_sec}s-merged/movns-pareto-set.csv",
    ]
    return next((p for p in candidates if os.path.exists(p)), "")


def mean_std(vals):
    if not vals:
        return 0.0, 0.0
    arr = np.array(vals)
    return float(arr.mean()), float(arr.std())


def main():
    parser = argparse.ArgumentParser(description="Plot MOVNS vs NSGA-II metrics over multiple seeds.")
    parser.add_argument("--time", type=int, default=240, help="Time budget in seconds (default: 240)")
    parser.add_argument("--runs", type=int, default=30, help="Number of seeds/runs (default: 30)")
    args = parser.parse_args()

    labels = ["HV", "IGD", "Spread", "Pareto", "Eps"]
    metrics_m = {l: [] for l in labels}
    metrics_n = {l: [] for l in labels}

    for k in range(1, args.runs + 1):
        nsga_path = pick_nsga(args.time, k)
        mov_path = pick_movns(args.time, k)
        nsga = load_pareto(nsga_path)
        mov = load_pareto(mov_path)
        if not nsga or not mov:
            print(f"run {k:02d}: missing files (NSGA: {bool(nsga)}, MOVNS: {bool(mov)})")
            continue
        ref = nsga + mov
        rp = compute_ref_point(ref)
        metrics_n["HV"].append(hypervolume(nsga, rp))
        metrics_m["HV"].append(hypervolume(mov, rp))
        metrics_n["IGD"].append(igd(nsga, ref))
        metrics_m["IGD"].append(igd(mov, ref))
        metrics_n["Spread"].append(spread(nsga))
        metrics_m["Spread"].append(spread(mov))
        metrics_n["Pareto"].append(len(nsga))
        metrics_m["Pareto"].append(len(mov))
        metrics_m["Eps"].append(epsilon(nsga, mov))  # eps(M vs N)
        metrics_n["Eps"].append(epsilon(mov, nsga))  # eps(N vs M)

    means_m = []; stds_m = []; means_n = []; stds_n = []
    for l in labels:
        m, s = mean_std(metrics_m[l]); means_m.append(m); stds_m.append(s)
        m2, s2 = mean_std(metrics_n[l]); means_n.append(m2); stds_n.append(s2)

    fig, axes = plt.subplots(1, len(labels), figsize=(14, 4))
    for ax, lab, m_mean, m_std, n_mean, n_std in zip(axes, labels, means_m, stds_m, means_n, stds_n):
        ax.bar(["MOVNS", "NSGA-II"], [m_mean, n_mean], yerr=[m_std, n_std],
               color=["#80b1d3", "#fdb462"], capsize=4)
        ax.set_title(lab)
        ax.set_ylabel("Mean ± Std")
    plt.suptitle("Comparison of MOVNS and NSGA-II (Multi-objective Metrics)")
    plt.tight_layout(rect=[0, 0, 1, 0.92])
    os.makedirs("results", exist_ok=True)
    out = f"results/metrics_comparison_{args.time}s.png"
    plt.savefig(out, dpi=150)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
