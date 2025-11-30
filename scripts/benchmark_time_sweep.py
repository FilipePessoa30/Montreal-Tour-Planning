#!/usr/bin/env python3
"""
Benchmark NSGA-II vs MOVNS with equal wall-clock time budgets.

For each time budget (default: 60s, 120s, ..., 600s), the script:
1) Runs NSGA-II with --max-time <budget> and saves in results/run-<budget>s/.
2) Runs MOVNS with --max-time <budget> and saves in movns-results/run-<budget>s/.
3) Loads the generated CSVs, computes quality metrics (hypervolume, spread, Pareto size),
   and reports the extreme solutions (best F1, best F2, best F3, best F4).

Usage (PowerShell from repo root):
  python scripts/benchmark_time_sweep.py
Optional flags:
  --times 60 120 180       # custom time budgets in seconds
  --no-run                 # skip running algorithms, just read existing CSVs and report metrics
"""

import argparse
import csv
import os
import subprocess
import sys
import time
from typing import List, Tuple, Dict, Any

MAXIMIZE = [True, True, False, False]
PADDING = 1.05  # small cushion above observed maxima


# ---------------------------- Utility: dominance & Pareto front ---------------------------- #
def dominates(p: List[float], q: List[float], maximize: List[bool]) -> bool:
    better = False
    for i, is_max in enumerate(maximize):
        if is_max:
            if p[i] < q[i]:
                return False
            if p[i] > q[i]:
                better = True
        else:
            if p[i] > q[i]:
                return False
            if p[i] < q[i]:
                better = True
    return better


def pareto_front(points: List[List[float]], maximize: List[bool]) -> List[List[float]]:
    front = []
    for p in points:
        if not any(dominates(q, p, maximize) for q in points if q is not p):
            front.append(p)
    return front


# ---------------------------- Metrics: HV and Spread ---------------------------- #
def normalize(points: List[List[float]], reference: List[float], maximize: List[bool]) -> List[List[float]]:
    normalized = []
    for obj in points:
        norm = []
        for i, val in enumerate(obj):
            ref = reference[i]
            if ref == 0:
                norm.append(0.0)
                continue
            if maximize[i]:
                # Higher is better: map to (ref - val)/ref so 0 = best, 1 = worst
                n = (ref - val) / ref
            else:
                # Lower is better: map to val/ref so 0 = best, 1 = worst
                n = val / ref
            # Keep inside [0, 1] to avoid negative/overflow
            norm.append(min(max(n, 0.0), 1.0))
        if all(0.0 <= v <= 1.0 for v in norm):
            normalized.append(norm)
    return normalized


def hypervolume(points: List[List[float]], reference: List[float], maximize: List[bool]) -> float:
    norm = normalize(points, reference, maximize)
    if not norm:
        return 0.0
    hv = 0.0
    for p in norm:
        contrib = 1.0
        for v in p:
            contrib *= (1.0 - v)
        hv += contrib
    # Average contribution (aligned with nsga2/metrics.py style)
    return hv / len(norm)


def spread(points: List[List[float]], maximize: List[bool]) -> float:
    if len(points) < 2:
        return 1.0
    num_obj = len(points[0])
    total = 0.0
    for m in range(num_obj):
        values = sorted([p[m] for p in points])
        if len(values) < 2:
            continue
        f_min, f_max = values[0], values[-1]
        if f_max == f_min:
            continue
        distances = [values[i + 1] - values[i] for i in range(len(values) - 1)]
        if not distances:
            continue
        mean_d = sum(distances) / len(distances)
        if mean_d == 0:
            continue
        d_f = abs(values[0] - f_min)
        d_l = abs(values[-1] - f_max)
        sum_diff = sum(abs(d - mean_d) for d in distances)
        spread_m = (d_f + d_l + sum_diff) / (d_f + d_l + len(distances) * mean_d)
        total += spread_m
    return total / num_obj if num_obj > 0 else 1.0


def epsilon_indicator(points1: List[List[float]], points2: List[List[float]]) -> float:
    """
    Additive epsilon indicator (points2 vs points1), adapted from movns.metrics.
    Lower is better for points2; requires both sets non-empty.
    """
    if not points1 or not points2:
        return float("inf")

    import numpy as np  # local import to avoid hard dependency if not installed

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

    if not eps_values:
        return float("inf")

    epsilon = max(eps_values)
    # clamp to reasonable bounds
    return max(-1.0, min(1.0, float(epsilon)))


def compute_metrics(points: List[List[float]]) -> Dict[str, float]:
    front = pareto_front(points, MAXIMIZE)
    if not front:
        return {"hypervolume": 0.0, "spread": 1.0, "pareto_size": 0}
    ref = compute_reference_point(points)
    return {
        "hypervolume": hypervolume(front, ref, MAXIMIZE),
        "spread": spread(front, MAXIMIZE),
        "pareto_size": len(front),
    }


def compute_reference_point(points: List[List[float]]) -> List[float]:
    """
    Build a reference point from observed maxima (for max objectives) and maxima (worst) for min objectives,
    padded by PADDING. This keeps HV comparable and data-driven.
    """
    if not points:
        return [20.0, 100.0, 1500.0, 1000.0]
    num_obj = len(points[0])
    ref = [0.0] * num_obj
    for j in range(num_obj):
        vals = [p[j] for p in points]
        worst = max(vals)  # use max for both, padding handles direction
        ref[j] = worst * PADDING if worst != 0 else 1.0
    return ref


# ---------------------------- Loaders ---------------------------- #
def load_nsga(path: str) -> Tuple[List[List[float]], List[Dict[str, Any]]]:
    rows = []
    if not os.path.exists(path):
        return [], rows
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for r in reader:
            rows.append(r)
    points = []
    for r in rows:
        try:
            points.append([
                float(r["TotalAttractions"]),
                float(r["TotalQuality"]),
                float(r["TotalTime"]),
                float(r["TotalCost"]),
            ])
        except Exception:
            continue
    return points, rows


def load_movns(path: str) -> Tuple[List[List[float]], List[Dict[str, Any]]]:
    rows = []
    if not os.path.exists(path):
        return [], rows
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for r in reader:
            rows.append(r)
    points = []
    for r in rows:
        try:
            points.append([
                float(r["TotalAttractions"]),
                float(r["TotalQuality"]),
                float(r["TotalTime"]),
                float(r["TotalCost"]),
            ])
        except Exception:
            continue
    return points, rows


# ---------------------------- Extremes ---------------------------- #
def extremes(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    if not rows:
        return {}
    key_f1 = max(rows, key=lambda r: float(r["TotalAttractions"]))
    key_f2 = max(rows, key=lambda r: float(r["TotalQuality"]))
    key_f3 = min(rows, key=lambda r: float(r["TotalTime"]))
    key_f4 = min(rows, key=lambda r: float(r["TotalCost"]))
    return {"F1": key_f1, "F2": key_f2, "F3": key_f3, "F4": key_f4}


# ---------------------------- Runner ---------------------------- #
def run_algorithms(budgets: List[int], do_run: bool) -> None:
    summary_rows = []
    for t in budgets:
        print(f"\n=== Tempo {t}s ===")
        # Try root-level results first; fallback to nsga2/results if user ran from nsga2/main.py with relative output
        nsga_out_dir = os.path.join("results", f"run-{t}s")
        nsga_alt_out_dir = os.path.join("nsga2", "results", f"run-{t}s")
        if not os.path.exists(os.path.join(nsga_out_dir, "nsga2-output.csv")) and \
           os.path.exists(os.path.join(nsga_alt_out_dir, "nsga2-output.csv")):
            nsga_out_dir = nsga_alt_out_dir

        movns_out_dir = os.path.join("movns-results", f"run-{t}s")
        nsga_csv = os.path.join(nsga_out_dir, "nsga2-output.csv")
        movns_csv = os.path.join(movns_out_dir, "movns-pareto-set.csv")

        if do_run:
            os.makedirs(nsga_out_dir, exist_ok=True)
            os.makedirs(movns_out_dir, exist_ok=True)

            print(f"NSGA-II -> {nsga_out_dir}")
            subprocess.run([
                sys.executable, "main.py",
                "--output-dir", nsga_out_dir,
                "--max-time", str(t)
            ], cwd="nsga2", check=True)

            print(f"MOVNS   -> {movns_out_dir}")
            subprocess.run([
                sys.executable, "-m", "movns.run",
                "--attractions", "places/attractions.csv",
                "--hotels", "places/hotels.csv",
                "--matrices", ".",
                "--solutions", "20",
                "--iterations", "100000",
                "--no-improvement", "100000",
                "--output", movns_out_dir,
                "--max-time", str(t)
            ], check=True)

        # Load all points to build a joint reference point per budget
        nsga_points, nsga_rows = load_nsga(nsga_csv)
        movns_points, movns_rows = load_movns(movns_csv)
        all_points = nsga_points + movns_points
        ref = compute_reference_point(all_points)

        # epsilon indicators (each vs the other)
        eps_nsga_vs_movns = epsilon_indicator(nsga_points, movns_points) if nsga_points and movns_points else None
        eps_movns_vs_nsga = epsilon_indicator(movns_points, nsga_points) if nsga_points and movns_points else None

        for label, points, rows, eps_vs_other in [
            ("NSGA-II", nsga_points, nsga_rows, eps_nsga_vs_movns),
            ("MOVNS", movns_points, movns_rows, eps_movns_vs_nsga),
        ]:
            if not points:
                print(f"{label}: sem dados em {nsga_csv if label=='NSGA-II' else movns_csv}")
                continue
            front = pareto_front(points, MAXIMIZE)
            m = {
                "hypervolume": hypervolume(front, ref, MAXIMIZE),
                "spread": spread(front, MAXIMIZE),
                "pareto_size": len(front),
            }
            ex = extremes(rows)
            eps_txt = f" | Epsilon_vs_other={eps_vs_other:.4f}" if eps_vs_other is not None else ""
            print(f"{label}: HV={m['hypervolume']:.4f} | Spread={m['spread']:.4f} | Pareto={m['pareto_size']}{eps_txt}")
            if ex:
                print(f"  Melhor F1 (atrações): {ex['F1']['TotalAttractions']} | Hotel: {ex['F1'].get('Hotel','-')}")
                print(f"  Melhor F2 (qualidade): {ex['F2']['TotalQuality']} | Hotel: {ex['F2'].get('Hotel','-')}")
                print(f"  Melhor F3 (tempo): {ex['F3']['TotalTime']} | Hotel: {ex['F3'].get('Hotel','-')}")
                print(f"  Melhor F4 (custo): {ex['F4']['TotalCost']} | Hotel: {ex['F4'].get('Hotel','-')}")
            if ex:
                summary_rows.append({
                    "time_sec": t,
                    "algo": label,
                    "hypervolume": m["hypervolume"],
                    "spread": m["spread"],
                    "pareto_size": m["pareto_size"],
                    "epsilon_vs_other": eps_vs_other if eps_vs_other is not None else "",
                    "best_F1_attractions": ex["F1"]["TotalAttractions"],
                    "best_F1_hotel": ex["F1"].get("Hotel", "-"),
                    "best_F2_quality": ex["F2"]["TotalQuality"],
                    "best_F2_hotel": ex["F2"].get("Hotel", "-"),
                    "best_F3_time": ex["F3"]["TotalTime"],
                    "best_F3_hotel": ex["F3"].get("Hotel", "-"),
                    "best_F4_cost": ex["F4"]["TotalCost"],
                    "best_F4_hotel": ex["F4"].get("Hotel", "-"),
                })

    # persist summary
    if summary_rows:
        out_dir = "results"
        os.makedirs(out_dir, exist_ok=True)
        out_csv = os.path.join(out_dir, "benchmark-summary.csv")
        cols = [
            "time_sec", "algo", "hypervolume", "spread", "pareto_size", "epsilon_vs_other",
            "best_F1_attractions", "best_F1_hotel",
            "best_F2_quality", "best_F2_hotel",
            "best_F3_time", "best_F3_hotel",
            "best_F4_cost", "best_F4_hotel",
        ]
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            import csv
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            for row in summary_rows:
                writer.writerow(row)
        print(f"\nResumo salvo em {out_csv}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NSGA-II and MOVNS with equal time budgets and compare metrics.")
    parser.add_argument("--times", nargs="+", type=int,
                        help="List of time budgets in seconds (default: 60 120 ... 600)")
    parser.add_argument("--no-run", action="store_true",
                        help="Do not execute algorithms; only read existing CSVs and report metrics.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    budgets = args.times if args.times else list(range(60, 601, 60))
    run_algorithms(budgets, do_run=not args.no_run)


if __name__ == "__main__":
    main()
