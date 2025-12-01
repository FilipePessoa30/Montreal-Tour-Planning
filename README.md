# Montreal Tour Planning

## Project Overview
This project implements two metaheuristics for a two-day tourist itinerary in Montreal:
- MOVNS (Multi-Objective Variable Neighborhood Search)
- NSGA-II

Objectives (optimized simultaneously):
1. Maximize number of attractions
2. Maximize total quality (rating/relevance)
3. Minimize total travel time (transit + visit)
4. Minimize total monetary cost (entrance + paid transport)

Key constraints: day window 08:00-20:00; POI opening hours respected; no POI repeated; routes start/end at the hotel; valid modes (walk, subway, bus, car).

## Operational Constraints
- Each day: 08:00-20:00 (480-1200 min)
- POIs have opening hours and fixed visit time
- No POI visited twice
- Daily route starts/ends at hotel
- Only valid transport modes

## Solution Representation
Two ordered sequences of POIs (Day 1, Day 2) plus transport modes between them.

## Neighborhood Structures (MOVNS)
1. N1: Internal swap — swap two POIs in the same day
2. N2: Cross-day move — move one POI between days
3. N3: Insert/Remove — add a new POI or drop one
4. N4: Substitution — replace a visited POI by an unvisited one
5. N5: 2-opt reversal — reverse a segment in one daily route
6. N6: Change hotel — switch the hotel and re-evaluate routes
7. N7: Change transport mode — change the transport mode of a segment

## Initial Archive Generation (MOVNS)
- Heuristic seeds (max attractions, max rating, min cost, min travel time, balanced)
- Random-feasible routes (sample subset, permute into days, repair time, dedup), sized by `--solutions` (CLI default: 20, configurable)

## MOVNS Framework
- External elitist archive (cap configurable; default 30, CLI default 60)
- Iterate neighborhoods with intensification/diversification

### Pseudocode (informal)
```
Input: archive A (|A| ~ 20), neighborhoods N1..N7, Tmax = 120 s or 30 idle loops
k_max = 5
repeat
    R = next solution in A (round-robin)
    k = 1
    while k <= k_max do
        R'  = Shake(R, Nk)                // random move of size k
        R'' = ParetoLocalSearch(R')       // VND on N1..N7
        if R'' is non-dominated w.r.t A then
            A = A ∪ {R''}; purge dominated
            HV-truncate(A, cap)
            k = 1     // intensify
        else
            k = k+1   // diversify
        end if
    end while
until CPU >= Tmax or 30 loops with no HV increase
return archive A
```

### Local Search Options
1. Weighted descent: random weights λ (Σλ=1), minimize F=Σλᵢ fᵢ
2. Pareto Local Search: explore all neighbors, keep non-dominated, repeat until stable

## Quality Monitoring
- Hyper-volume (HV)
- Spread (Delta) — if Delta > 0.35 for 50 iterations, jump to N5
- Additive epsilon-indicator — compare A_t with A_{t-10}; stop early if epsilon < 0.05 for 3 windows
- Inverted Generational Distance (IGD) — distance from a reference Pareto to the current front (lower is better)

## Hyper-parameters (current defaults)
| Parameter                   | Value                                               | Rationale                         |
| --------------------------- | --------------------------------------------------- | --------------------------------- |
| Initial archive (solutions) | 20 (CLI default)                                    | Small seed, fast start            |
| k_max                       | 5                                                   | As in GVNS                        |
| Shake depth                 | k                                                   | Classical GVNS                    |
| Archive cap                 | 60 (CLI default)                                    | HV truncation with more diversity |
| Stop rule                   | Time budget (`--max-time`) or iterations/idle loops | Use time as primary stopper       |

## Outputs
1. `route_solution.csv` — itinerary details
2. `movns_execution_log.csv` — per-iteration metrics (iteration, HV, Delta, epsilon, F1–F4, k, archive size)
3. NSGA-II runs: `nsga2-output.csv`, `nsga2-pareto-set.csv`, `nsga2-metrics.csv`
4. MOVNS runs: `movns-pareto-set.csv`, `movns-metrics.csv`, `movns-initial-population.csv`

## Project Structure
- `main.py` — CLI to run MOVNS
- `movns/` — Core MOVNS (`movns.py`, `constructor.py`, `metrics.py`, `logger.py`, `run.py`)
- `nsga2/` — NSGA-II (has its own `main.py`)
- `scripts/` — Experiments and evaluation
  - `benchmark_time_sweep.py` — runs by time budget
  - `merge_movns_runs.py` — merge Pareto sets of multiple MOVNS runs
  - `compare_hv_runs.py` — compare HV, spread, Pareto size, epsilon, IGD per seed
- `models.py`, `utils.py`, `verify_solutions.py`
- Data: `places/`, `travel-times/`

## Experiments (30 runs, fixed 240 s)

### NSGA-II (weakened)
- Params: `--population-size 40 --generations 20 --crossover-prob 0.6 --mutation-prob 0.5`
- Time per run: 240 s
- Run 30x (implicit seeds 1..30):
```powershell
$time = 240
$runs = 1..30
foreach ($r in $runs) {
  python .\nsga2\main.py --output-dir ("results/run-${time}s-nsga-$r") --max-time $time `
    --population-size 40 --generations 20 --crossover-prob 0.6 --mutation-prob 0.5
}
```

### MOVNS (light)
- Params: `--solutions 4 --no-improvement 2 --archive-max 60` (others default; high `--iterations`, stop by time)
- Time per run: 240 s
- Run 30x (implicit seeds 1..30):
```powershell
$time = 240
$runs = 1..30
foreach ($r in $runs) {
  python -m movns.run --attractions places/attractions.csv --hotels places/hotels.csv --matrices . `
    --solutions 4 --iterations 100000 --no-improvement 2 --archive-max 60 `
    --output ("movns-results/run-${time}s-movns-$r") --max-time $time
}
```

### Compare 30 seeds (HV, IGD, spread, Pareto size, epsilon)
```powershell
python scripts\compare_hv_runs.py --time 240 --runs 30
```

### Summary (240 s, 30 seeds)
- Seeds: implicit 1..30 (from folder index)
- HV: MOVNS won 26/30
- IGD: MOVNS won 30/30 (lower is better)
- Spread: MOVNS won 5/30
- Pareto size: MOVNS won 30/30
- Epsilon (lower is better): MOVNS won 0/30
