# Montreal Tour Planning

## Project Overview

This project implements two metaheuristics for planning a two-day tourist itinerary in Montreal:
- **MOVNS** (Multi-Objective Variable Neighborhood Search)
- **NSGA-II**

Objectives (to optimize simultaneously):
1. Maximize number of attractions
2. Maximize total quality (rating/relevance)
3. Minimize total travel time
4. Minimize total monetary cost

Key constraints: 08:00–20:00 window each day; POI opening hours respected; no POI repeated; routes start/end at the hotel; only valid transport modes (walk, subway, bus, car).

## MOVNS (high level)
- Solution: ordered POIs for Day 1 and Day 2, plus transport modes.
- Neighborhoods: swap within day; move between days; insert/remove; substitution; 2-opt reversal.
- Archive: elitist, truncated by HV; typical cap 30 (configurable).
- Stop: time budget or idle loops.

## NSGA-II (high level)
- Standard NSGA-II with crossover, mutation, non-dominated sorting, crowding distance.
- Configurable population, generations, crossover and mutation rates.

## Outputs
1. `route_solution.csv` – itinerary details
2. `movns_execution_log.csv` – per-iteration metrics (iteration, HV, Delta, epsilon, F1–F4, k, archive size)
3. For NSGA-II runs: `nsga2-output.csv`, `nsga2-pareto-set.csv`, `nsga2-metrics.csv`
4. For MOVNS runs: `movns-pareto-set.csv`, `movns-metrics.csv`, `movns-initial-population.csv`

## Project Structure
- `main.py` – CLI to run MOVNS
- `movns/` – Core MOVNS implementation (`movns.py`, `constructor.py`, `metrics.py`, `logger.py`, `run.py`)
- `nsga2/` – NSGA-II implementation (with its own `main.py`)
- `scripts/` – Experiment and evaluation helpers  
  - `benchmark_time_sweep.py` – runs by time budget  
  - `merge_movns_runs.py` – merge Pareto sets of multiple MOVNS runs  
  - `compare_hv_runs.py` – compare metrics (HV, spread, Pareto size, epsilon) per seed  
- `models.py`, `utils.py`, `verify_solutions.py`
- Data: `places/`, `travel-times/`

## Experiments (30 runs, fixed 240 s)

### NSGA-II 
- Params: `--population-size 40 --generations 20 --crossover-prob 0.6 --mutation-prob 0.5`
- Time per run: 240 s
- Run 30x (seeds implicit via folder index):
```powershell
$time = 240
$runs = 1..30
foreach ($r in $runs) {
  python .\nsga2\main.py --output-dir ("results/run-${time}s-nsga-$r") --max-time $time `
    --population-size 40 --generations 20 --crossover-prob 0.6 --mutation-prob 0.5
}
```

### MOVNS
- Params: `--solutions 4 --no-improvement 2 --archive-max 60` (others default; high `--iterations`, stop by time)
- Time per run: 240 s
- Run 30x (seeds implicit via folder index):
```powershell
$time = 240
$runs = 1..30
foreach ($r in $runs) {
  python -m movns.run --attractions places/attractions.csv --hotels places/hotels.csv --matrices . `
    --solutions 4 --iterations 100000 --no-improvement 2 --archive-max 60 `
    --output ("movns-results/run-${time}s-movns-$r") --max-time $time
}
```

### Compare the 30 seeds (HV, spread, Pareto size, epsilon)
```powershell
python scripts\compare_hv_runs.py --time 240 --runs 30
```

### Summary (240 s, 30 seeds)
- Seeds: implicit 1..30 (from folder index)
- HV: MOVNS won 24/30
- Spread: MOVNS won 5/30
- Pareto size: MOVNS won 30/30
- Epsilon (lower is better): MOVNS won 0/30
