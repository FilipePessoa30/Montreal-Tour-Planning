#!/usr/bin/env python3
"""
Compare NSGA-II vs MOVNS run by run for a single time budget, reporting hypervolume wins.

Default expects:
  - NSGA-II paretos in:  results/run-<time>s-nsga-<k>/nsga2-pareto-set.csv
  - MOVNS paretos in:    movns-results/run-<time>s-movns-<k>/movns-pareto-set.csv

Usage (PowerShell, repo root):
  python scripts/compare_hv_runs.py --time 240 --runs 30
"""

import argparse
import csv
import os
from typing import List, Sequence

REF_POINT = [20.0, 100.0, 1500.0, 1000.0]
MAXIMIZE = [True, True, False, False]


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


def normalize(points: Sequence[Sequence[float]]) -> List[List[float]]:
    norm = []
    for p in points:
        n = []
        for v, ref, is_max in zip(p, REF_POINT, MAXIMIZE):
            if ref == 0:
                n.append(0.0)
                continue
            n.append((ref - v) / ref if is_max else v / ref)
        if all(0.0 <= x <= 1.0 for x in n):
            norm.append(n)
    return norm


def hypervolume(points: Sequence[Sequence[float]]) -> float:
    n = normalize(points)
    if not n:
        return 0.0
    hv = 0.0
    for p in n:
        c = 1.0
        for v in p:
            c *= (1.0 - v)
        hv += c
    return hv / len(n)


def igd(solutions: Sequence[Sequence[float]], reference: Sequence[Sequence[float]]) -> float:
    """
    Inverted Generational Distance: average distance from each ref point to nearest solution.
    Lower is better for 'solutions' vs 'reference'.
    """
    import math
    if not solutions or not reference:
        return float("inf")
    total = 0.0
    for ref_pt in reference:
        best = float("inf")
        for sol in solutions:
            d = 0.0
            for a, b in zip(ref_pt, sol):
                d += (a - b) ** 2
            d = math.sqrt(d)
            if d < best:
                best = d
        total += best
    return total / len(reference)


def spread(points: Sequence[Sequence[float]]) -> float:
    if len(points) < 2:
        return 1.0
    m = len(points[0])
    total = 0.0
    for j in range(m):
        vals = sorted(p[j] for p in points)
        if len(vals) < 2:
            continue
        f_min, f_max = vals[0], vals[-1]
        if f_max == f_min:
            continue
        d = [vals[i+1] - vals[i] for i in range(len(vals)-1)]
        if not d:
            continue
        mean = sum(d) / len(d)
        if mean == 0:
            continue
        d_f = abs(vals[0] - f_min)
        d_l = abs(vals[-1] - f_max)
        sum_diff = sum(abs(x - mean) for x in d)
        total += (d_f + d_l + sum_diff) / (d_f + d_l + len(d)*mean)
    return total / m if m else 1.0


def epsilon_indicator(points1: Sequence[Sequence[float]], points2: Sequence[Sequence[float]]) -> float:
    """
    Additive epsilon (points2 vs points1); lower is better for points2.
    """
    import numpy as np
    if not points1 or not points2:
        return float("inf")
    obj1 = np.array(points1, dtype=float)
    obj2 = np.array(points2, dtype=float)
    min_vals = np.min(np.vstack([obj1, obj2]), axis=0)
    max_vals = np.max(np.vstack([obj1, obj2]), axis=0)
    ranges = max_vals - min_vals
    ranges[ranges == 0] = 1.0
    norm1 = np.zeros_like(obj1, dtype=float)
    norm2 = np.zeros_like(obj2, dtype=float)
    for i, is_max in enumerate(MAXIMIZE):
        if is_max:
            norm1[:, i] = (obj1[:, i] - min_vals[i]) / ranges[i]
            norm2[:, i] = (obj2[:, i] - min_vals[i]) / ranges[i]
        else:
            norm1[:, i] = 1.0 - (obj1[:, i] - min_vals[i]) / ranges[i]
            norm2[:, i] = 1.0 - (obj2[:, i] - min_vals[i]) / ranges[i]
    eps_values = []
    for sol2 in norm2:
        min_eps = float("inf")
        for sol1 in norm1:
            diffs = sol2 - sol1
            max_diff = np.max(diffs)
            if max_diff < min_eps:
                min_eps = max_diff
        eps_values.append(min_eps)
    return max(eps_values) if eps_values else float("inf")


def compare_runs(time_sec: int, runs: int) -> None:
    wins_hv = wins_spread = wins_pareto = wins_eps = wins_igd = 0
    total = 0
    for k in range(1, runs + 1):
        # NSGA-II paths
        nsga_candidates = [
            f"results/run-{time_sec}s-nsga-{k}/nsga2-pareto-set.csv",             # se você rodou nsga com sufixo -nsga-k em results/
            f"nsga2/results/run-{time_sec}s-nsga-{k}/nsga2-pareto-set.csv",       # idem dentro de nsga2/
            f"results/run-{time_sec}s/nsga2-pareto-set.csv",                      # base em results/
            f"nsga2/results/run-{time_sec}s/nsga2-pareto-set.csv",                # base em nsga2/
        ]
        nsga_path = next((p for p in nsga_candidates if os.path.exists(p)), "")

        # MOVNS paths
        movns_candidates = [
            f"movns-results/run-{time_sec}s-movns-{k}/movns-pareto-set.csv",      # sufixo -movns-k
            f"movns-results/run-{time_sec}s/movns-pareto-set.csv",                # base
            f"movns-results/run-{time_sec}s-merged/movns-pareto-set.csv",         # pareto mesclado
        ]
        movns_path = next((p for p in movns_candidates if os.path.exists(p)), "")

        nsga_pts = load_pareto(nsga_path)
        movns_pts = load_pareto(movns_path)
        if not nsga_pts or not movns_pts:
            print(f"run {k:02d}: faltam arquivos (NSGA: {bool(nsga_pts)}, MOVNS: {bool(movns_pts)})")
            continue
        hv_nsga = hypervolume(nsga_pts)
        hv_movns = hypervolume(movns_pts)
        ref = nsga_pts + movns_pts
        igd_nsga = igd(nsga_pts, ref)
        igd_movns = igd(movns_pts, ref)
        spread_nsga = spread(nsga_pts)
        spread_movns = spread(movns_pts)
        eps_movns_vs_nsga = epsilon_indicator(nsga_pts, movns_pts)
        eps_nsga_vs_movns = epsilon_indicator(movns_pts, nsga_pts)
        pareto_nsga = len(nsga_pts)
        pareto_movns = len(movns_pts)

        total += 1
        if hv_movns > hv_nsga:
            wins_hv += 1
        if spread_movns < spread_nsga:
            wins_spread += 1
        if pareto_movns > pareto_nsga:
            wins_pareto += 1
        if eps_movns_vs_nsga < eps_nsga_vs_movns:
            wins_eps += 1
        if igd_movns < igd_nsga:
            wins_igd += 1

        print(f"run {k:02d}: "
              f"HV N={hv_nsga:.4f} M={hv_movns:.4f} | "
              f"IGD N={igd_nsga:.4f} M={igd_movns:.4f} | "
              f"Spread N={spread_nsga:.4f} M={spread_movns:.4f} | "
              f"Pareto N={pareto_nsga} M={pareto_movns} | "
              f"eps(M vs N)={eps_movns_vs_nsga:.4f} eps(N vs M)={eps_nsga_vs_movns:.4f}")

    if total == 0:
        print("\nNenhuma execução válida encontrada.")
        return
    print(f"\nResumo {time_sec}s em {total} runs:")
    print(f"  HV: MOVNS venceu {wins_hv}/{total}")
    print(f"  IGD: MOVNS venceu {wins_igd}/{total} (menor é melhor)")
    print(f"  Spread: MOVNS venceu {wins_spread}/{total}")
    print(f"  Pareto size: MOVNS venceu {wins_pareto}/{total}")
    print(f"  epsilon (menor é melhor): MOVNS venceu {wins_eps}/{total}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare HV do NSGA-II vs MOVNS por seed.")
    parser.add_argument("--time", type=int, default=240, help="Tempo em segundos (default: 240)")
    parser.add_argument("--runs", type=int, default=30, help="Número de execuções/seed (default: 30)")
    args = parser.parse_args()
    compare_runs(args.time, args.runs)


if __name__ == "__main__":
    main()
