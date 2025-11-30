#!/usr/bin/env python3
"""
Main entry point for Montreal tour planning system.
Implements MOVNS algorithm for route optimization.
"""

import os
import sys
import argparse
from movns.run import run_movns

def main():
    parser = argparse.ArgumentParser(description='Montreal Tour Planning with MOVNS')
    parser.add_argument('--attractions', default='places/attractions.csv',
                        help='Path to attractions data file')
    parser.add_argument('--hotels', default='places/hotels.csv',
                        help='Path to hotels data file')
    parser.add_argument('--matrices', default='.',
                        help='Path to transport matrices directory')
    parser.add_argument('--solutions', type=int, default=20,
                        help='Initial population size (archive will be capped at 30)')
    parser.add_argument('--iterations', type=int, default=120,
                        help='Maximum number of iterations')
    parser.add_argument('--no-improv-stop', type=int, default=30,
                        help='Stop after N iterations without improvement')
    parser.add_argument('--output', default='movns-results',
                        help='Output directory for results')
    parser.add_argument('--archive-max', type=int, default=60,
                        help='Maximum size of Pareto archive (default: 60)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.attractions):
        print(f"Error: Attractions file not found: {args.attractions}")
        sys.exit(1)
    if not os.path.exists(args.hotels):
        print(f"Error: Hotels file not found: {args.hotels}")
        sys.exit(1)
    
    try:
        run_movns(
            attractions_file=args.attractions,
            hotels_file=args.hotels,
        matrices_path=args.matrices,
        solution_count=args.solutions,
        iterations=args.iterations,
        no_improv_stop=args.no_improv_stop,
        output_dir=args.output,
        archive_max=args.archive_max
    )
    except Exception as e:
        print(f"Error running MOVNS: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
