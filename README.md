# Montreal Tour Planning - Multi-Objective Variable Neighborhood Search (MOVNS)

## Project Overview

This project implements a Multi-Objective Variable Neighborhood Search (MOVNS) algorithm for planning a two-day tourist itinerary in Montreal. The algorithm simultaneously optimizes four conflicting objectives:

1. **F1: Maximize the number of attractions** visited over both days
2. **F2: Maximize the total quality** (rating/relevance score) of all visited attractions
3. **F3: Minimize total travel time** (inter-attraction transit + visit durations)
4. **F4: Minimize total monetary cost** (entrance fees + paid transport)

## Operational Constraints

- Each day runs from 08:00 (480 min) to 20:00 (1200 min)
- Every Point of Interest (POI) has specific opening hours and fixed visit time
- No POI may be visited twice in the two days
- Each daily route starts and ends at the tourist's hotel
- Only valid transport modes (walking, subway, bus, car) may be used

## Solution Representation

An itinerary is encoded as two ordered sequences of attractions for Day 1 and Day 2, along with the associated transport modes between attractions.

## Neighborhood Structures

The MOVNS algorithm uses the following neighborhood structures:

1. **N₁: Internal swap** - Exchange two POIs in the same day
2. **N₂: Cross-day move** - Shift one POI from day 1 to day 2 or vice-versa
3. **N₃: Insert/Remove** - Add a new POI or drop an existing one
4. **N₄: Substitution** - Replace a visited POI by an unvisited one
5. **N₅: 2-opt reversal** - Reverse a segment in one daily route

## Initial Archive Generation

We start with an elitist seed archive of about 20 feasible itineraries:

### Five heuristic seeds
1. **Max-Attractions Greedy** - Insert POIs (highest rating first) until no further visit fits the daily time window
2. **Max-Rating Greedy** - Insert POIs by descending quality even if quantity is small
3. **Min-Cost Greedy** - Cheapest POIs first, skip any fee > $θ (user-set)
4. **Min-Travel-Time Greedy** - Build a tight cluster around the hotel (short arcs only)
5. **Balanced Heuristic** - Sequentially insert the POI with highest ratio quality/(visit_time+min_travel_time) while feasible

### Fifteen random-feasible routes
Each random seed is produced by:
1. Drawing a random subset of POIs (Bernoulli p=0.3)
2. Randomly permuting them into Day 1; spilling overflow into Day 2
3. Repairing time violations by dropping the last POI of each day
4. Removing duplicates

## MOVNS Framework

### External elitist archive A
- Initial archive: 20 solutions (5 heuristic + 15 random)
- At every insertion: add a solution if non-dominated, delete dominated solutions
- Cap size at A_max=30 using hyper-volume contribution truncation

### Pseudocode

```
Input : archive A (|A|≈20), N1..N5, Tmax=120 s or 30 idle loops
k_max ← 5
repeat
    R ← next solution in A (round-robin)
    k ← 1
    while k ≤ k_max do
        R'  ← Shake(R, Nk)                // random move of size k
        R'' ← ParetoLocalSearch(R')       // VND on N1..N5
        if R'' non-dominated by A then
            A ← A ∪ {R''}; purge dominated
            HV-truncate(A, 30)            // elitist, bounded
            k ← 1                         // intensify
        else
            k ← k+1                       // diversify
        end if
    end while
until CPU ≥ Tmax or 30 loops with no HV increase
return archive A
```

### Local Search Options
1. **Weighted descent**: Draw random weights λ such that Σλᵢ=1, minimize F=Σλᵢfᵢ
2. **Pareto Local Search**: Explore all neighbors, add every non-dominated neighbor to a local archive, iterate until none remains

## Quality Monitoring

- **Hyper-volume (HV)** - Measures convergence + diversity, monotone under elitism
- **Spread (Δ)** - Spacing indicator; if Δ>0.35 for 50 iterations, force a jump to N₅
- **Additive ε-indicator** - Compare A_t with A_{t-10}; early stop when ε<0.05 for three successive windows

## Hyper-parameters

| Parameter | Recommended value | Rationale |
|-----------|-------------------|-----------|
| Initial archive \|A₀\| | 20 routes | Fast convergence without loss of coverage |
| k_max | 5 neighborhoods | Diminishing returns beyond six |
| Shake depth | k | Classical GVNS rule |
| Archive cap A_max | 30 | HV-based truncation retains diversity |
| Stop rule | 120 s or 30 idle loops | Matches fast MOVNS benchmarks |

## Expected Outcome

MOVNS returns a Pareto front of feasible two-day routes, e.g., one solution may visit 12 medium-quality POIs (low cost, long travel), another 8 top-rated POIs (high quality, moderate travel/cost), etc.

Empirical studies show MOVNS often yields more non-dominated solutions than NSGA-II, thanks to stronger local refinement and fewer parameters.

## Outputs

1. `route_solution.csv` - Final itinerary (day, order, POI, start, end, transport, duration, cost, rating)
2. `movns_execution_log.csv` - Per-iteration data (iteration, HV, Δ, ε, F₁-F₄, k, archive size)

## Project Structure

- `movns/` - Core MOVNS implementation
  - `movns.py` - Base MOVNS algorithm
  - `neighborhoods.py` - Neighborhood structures
  - `constructor.py` - Initial solution constructor
  - `metrics.py` - Quality metrics (HV, Spread, Epsilon)
  - `enhanced_movns.py` - Enhanced algorithm with transport mode diversity
- `tools/` - Utility scripts for data processing and visualization
- `models.py` - Data models for Solution, Hotel, Attraction, etc.
- `utils.py` - Helper functions
- `verify_solutions.py` - Solution validation
- `pareto_visualizer.py` - Pareto front visualization

## Experimentos (30 execuções, tempo fixo 240 s)

### NSGA-II (parâmetros enfraquecidos)
- Parâmetros: `--population-size 40 --generations 20 --crossover-prob 0.6 --mutation-prob 0.5`
- Tempo por execução: 240 s
- Execução 30 vezes (seeds implícitas 1..30 via índice da pasta):
```powershell
$time = 240
$runs = 1..30
foreach ($r in $runs) {
  python .\nsga2\main.py --output-dir ("results/run-${time}s-nsga-$r") --max-time $time `
    --population-size 40 --generations 20 --crossover-prob 0.6 --mutation-prob 0.5
}
```

### MOVNS (parâmetros leves)
- Parâmetros: `--solutions 4 --no-improvement 2 --archive-max 60` (demais padrões; `--iterations` alto, parada por tempo)
- Tempo por execução: 240 s
- Execução 30 vezes (seeds implícitas 1..30 via índice da pasta):
```powershell
$time = 240
$runs = 1..30
foreach ($r in $runs) {
  python -m movns.run --attractions places/attractions.csv --hotels places/hotels.csv --matrices . `
    --solutions 4 --iterations 100000 --no-improvement 2 --archive-max 60 `
    --output ("movns-results/run-${time}s-movns-$r") --max-time $time
}
```

### Comparação das 30 seeds (HV, Spread, Pareto size, epsilon)
```powershell
python scripts\compare_hv_runs.py --time 240 --runs 30
```

### Resumo obtido (240 s, 30 seeds)
- HV: MOVNS venceu 24/30
- Spread: MOVNS venceu 5/30
- Pareto size: MOVNS venceu 30/30
- Epsilon (menor é melhor): MOVNS venceu 0/30
