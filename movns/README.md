# Optimized MOVNS Implementation for Montreal Tour Planning

This directory contains an optimized implementation of the Multi-Objective Variable Neighborhood Search (MOVNS) algorithm for the Montreal Tour Planning problem.

## Overview

The optimized MOVNS implementation addresses several performance issues found in the original implementation, particularly focusing on transport matrix loading, which was identified as the main performance bottleneck.

## Key Features

### Optimized Transport Matrix Loading

- **Class-level Static Caching**: Transport matrices are loaded only once for all MOVNS instances.
- **Preloading Mechanism**: A dedicated method for preloading all matrices before creating any MOVNS instances.
- **Entity Caching**: Hotels and attractions are cached to avoid unnecessary reloading.
- **Travel Time Memoization**: Travel times between locations are cached to avoid repeated calculations.

### Improved Transport Mode Selection

- **Adaptive Mode Selection**: Transport modes are selected with adaptive weighting to ensure mode diversity.
- **Subway Promotion**: Special boosting for subway mode to ensure its inclusion in solutions.
- **Mode Frequency Tracking**: Tracking of mode frequencies to balance usage across solutions.

### Solution Conversion Utilities

- **CSV Export**: Built-in methods for exporting solutions to CSV format for validation.
- **NSGA-II Compatibility**: Solutions are saved in NSGA-II compatible format for validation.

## Performance Improvements

- Eliminated redundant matrix loading, significantly reducing execution time.
- Reduced memory usage through shared caching across instances.
- Improved solution quality through better transport mode distribution.

## Usage

The main optimized implementation is in `optimized_movns.py`. It can be used as follows:

1. Preload all matrices and entities (recommended for best performance):

```python
from movns.optimized_movns import OptimizedMOVNS

# Preload data once at the beginning
OptimizedMOVNS.preload_matrices(
    attractions_file="places/attractions.csv",
    hotels_file="places/hotels.csv",
    matrices_path="results",
    verbose=True
)

# Create and run MOVNS instances (will use preloaded data)
movns = OptimizedMOVNS(output_dir="results/optimized_movns")
solutions = movns.run()
```

2. Or simply create and run (data will be loaded automatically):

```python
from movns.optimized_movns import OptimizedMOVNS

# Create and run MOVNS (will load data if not already loaded)
movns = OptimizedMOVNS()
solutions = movns.run()
```

## Running Tests

Use the `run_optimized_movns.py` script in the project root to run the algorithm:

```bash
python3 run_optimized_movns.py --quick-test  # For a quick test
python3 run_optimized_movns.py  # For a full run
```

To verify the quality of generated solutions, use the `verify_optimized_movns.py` script:

```bash
python3 verify_optimized_movns.py movns-results/optimized_movns_YYYYMMDD_HHMMSS/nsga2_format.csv
```

## Key Algorithm Parameters

- `max_archive_size`: Maximum number of solutions to keep in the Pareto front (default: 30)
- `max_iterations`: Maximum number of algorithm iterations (default: 100)
- `max_time`: Maximum execution time in seconds (default: 120)
- `max_idle_iterations`: Maximum iterations without improvement before stopping (default: 30)
- `k_max`: Maximum neighborhood index for VNS (default: 5)

## Output Files

The algorithm produces the following output files:

- `route_solution.csv`: Detailed solution information with all route details
- `nsga2_format.csv`: Solutions in NSGA-II compatible format for validation
- `movns_execution_log.csv`: Execution metrics for each iteration

## Performance Notes

This implementation significantly improves performance by:

1. Loading transport matrices once instead of for each instance
2. Caching travel time calculations
3. Using static entity caches for hotels and attractions
4. Implementing efficient matrix data structures

For best performance, always use the preloading mechanism when running multiple instances of MOVNS.