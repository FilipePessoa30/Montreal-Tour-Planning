import os
import sys
import argparse
from constructor import RouteConstructor
from nsga2 import NSGA2
from metrics import print_metrics, get_pareto_front, calculate_hypervolume, calculate_spread

def main():
    parser = argparse.ArgumentParser(description="Run NSGA-II for Montreal tour planning")
    parser.add_argument("--output-dir", default="results",
                        help="Directory where nsga2-output.csv will be written")
    parser.add_argument("--max-time", type=float, default=None,
                        help="Maximum wall-clock time in seconds (optional)")
    args = parser.parse_args()

    project_dir = os.path.dirname(os.path.abspath(__file__))
    attractions_file = os.path.join(project_dir, "places", "attractions.csv")
    hotels_file = os.path.join(project_dir, "places", "hotels.csv")
    matrices_path = project_dir
    output_dir = os.path.join(project_dir, args.output_dir)
    output_file = os.path.join(output_dir, "nsga2-output.csv")

    if not os.path.exists(attractions_file):
        print(f"Error: {attractions_file} not found")
        return 1
    if not os.path.exists(hotels_file):
        print(f"Error: {hotels_file} not found")
        return 1

    constructor = RouteConstructor(attractions_file, hotels_file, matrices_path)
    population_size = 200
    generations = 100
    crossover_prob = 0.90
    mutation_prob = 0.20

    nsga2 = NSGA2(constructor, population_size)
    initial_population = nsga2.initialize_population()
    print(f"Initial population: {len(initial_population)} solutions")

    final_population = nsga2.run(generations=generations,
                                 crossover_prob=crossover_prob,
                                 mutation_prob=mutation_prob,
                                 max_time=args.max_time)
    print(f"Final population: {len(final_population)} solutions")
    print(f"Final Pareto front size: {nsga2.pareto_front_sizes[-1]}")

    os.makedirs(output_dir, exist_ok=True)
    # full population
    constructor.export_population(final_population, output_file)
    print(f"Results exported to {output_file}")

    # Pareto set
    pareto_front = get_pareto_front(final_population)
    pareto_file = os.path.join(output_dir, "nsga2-pareto-set.csv")
    constructor.export_population(pareto_front, pareto_file)
    print(f"Pareto set exported to {pareto_file}")

    # Metrics + extremes
    metrics_file = os.path.join(output_dir, "nsga2-metrics.csv")
    reference_point = [20.0, 100.0, 1500.0, 1000.0]
    hv = calculate_hypervolume(pareto_front, reference_point)
    spread = calculate_spread(pareto_front)
    pareto_size = len(pareto_front)

    best_f1 = max(pareto_front, key=lambda s: s.get_objectives()[0]) if pareto_front else None
    best_f2 = max(pareto_front, key=lambda s: s.get_objectives()[1]) if pareto_front else None
    best_f3 = min(pareto_front, key=lambda s: s.get_objectives()[2]) if pareto_front else None
    best_f4 = min(pareto_front, key=lambda s: s.get_objectives()[3]) if pareto_front else None

    import csv
    with open(metrics_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(["Hypervolume", "Spread", "ParetoSize",
                         "BestF1_Attractions", "BestF1_Hotel",
                         "BestF2_Quality", "BestF2_Hotel",
                         "BestF3_Time", "BestF3_Hotel",
                         "BestF4_Cost", "BestF4_Hotel"])
        writer.writerow([
            f"{hv:.4f}", f"{spread:.4f}", pareto_size,
            best_f1.get_objectives()[0] if best_f1 else "",
            best_f1.hotel.name if best_f1 else "",
            best_f2.get_objectives()[1] if best_f2 else "",
            best_f2.hotel.name if best_f2 else "",
            best_f3.get_objectives()[2] if best_f3 else "",
            best_f3.hotel.name if best_f3 else "",
            best_f4.get_objectives()[3] if best_f4 else "",
            best_f4.hotel.name if best_f4 else "",
        ])
    print(f"Metrics exported to {metrics_file}")

    if final_population:
        best = max(final_population, key=lambda s: s.get_objectives()[0])
        obj = best.get_objectives()
        print(f"\nBest solution (max attractions):")
        print(f"  Hotel: {best.hotel.name}")
        print(f"  F1 (Attractions): {obj[0]:.0f}")
        print(f"  F2 (Quality): {obj[1]:.1f}")
        print(f"  F3 (Time): {obj[2]:.1f} min")
        print(f"  F4 (Cost): ${obj[3]:.2f}")
        print_metrics(final_population)
    return 0

if __name__ == "__main__":
    sys.exit(main())
