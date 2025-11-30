#!/usr/bin/env python3
"""
Merge multiple MOVNS Pareto sets for the same time budget into a single non-dominated set.

Assumes runs are stored under movns-results/run-<time>s-run<k>/movns-pareto-set.csv
and writes the merged front to movns-results/run-<time>s-merged/movns-pareto-set.csv
and movns-metrics.csv.

Usage (PowerShell, repo root):
  python scripts/merge_movns_runs.py --times 60 120 180 240 300 --runs 1 2 3
"""

import argparse
import csv
import os
from typing import List, Dict, Any

MAXIMIZE = [True, True, False, False]  # attractions, quality, time, cost


def dominates(p: List[float], q: List[float]) -> bool:
    better = False
    for i, is_max in enumerate(MAXIMIZE):
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


def load_runs(time_sec: int, runs: List[int]) -> List[Dict[str, Any]]:
    rows = []
    for r in runs:
        path = os.path.join("movns-results", f"run-{time_sec}s-run{r}", "movns-pareto-set.csv")
        if not os.path.exists(path):
            continue
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                try:
                    row["_objs"] = [
                        float(row["TotalAttractions"]),
                        float(row["TotalQuality"]),
                        float(row["TotalTime"]),
                        float(row["TotalCost"]),
                    ]
                    rows.append(row)
                except Exception:
                    continue
    return rows


def filter_pareto(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    pareto = []
    for r in rows:
        if any(dominates(o["_objs"], r["_objs"]) for o in rows if o is not r):
            continue
        pareto.append(r)
    return pareto


def write_pareto(time_sec: int, pareto: List[Dict[str, Any]]) -> None:
    out_dir = os.path.join("movns-results", f"run-{time_sec}s-merged")
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, "movns-pareto-set.csv")
    if not pareto:
        print(f"[{time_sec}s] Nenhuma solução para mesclar.")
        return
    fieldnames = [k for k in pareto[0].keys() if k != "_objs"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for r in pareto:
            writer.writerow({k: v for k, v in r.items() if k != "_objs"})
    print(f"[{time_sec}s] Pareto mesclado salvo em {out_csv} ({len(pareto)} soluções)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge multiple MOVNS runs into one Pareto set.")
    parser.add_argument("--times", nargs="+", type=int, required=True,
                        help="Lista de tempos em segundos (ex: 60 120 180)")
    parser.add_argument("--runs", nargs="+", type=int, required=True,
                        help="Lista de índices de execução (ex: 1 2 3)")
    args = parser.parse_args()

    for t in args.times:
        rows = load_runs(t, args.runs)
        pareto = filter_pareto(rows)
        write_pareto(t, pareto)


if __name__ == "__main__":
    main()
