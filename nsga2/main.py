import os
import sys
from constructor import RouteConstructor
from nsga2 import NSGA2
from metrics import print_metrics

def main():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    attractions_file = os.path.join(project_dir, "places", "attractions.csv")
    hotels_file = os.path.join(project_dir, "places", "hotels.csv")
    matrices_path = project_dir
    output_file = os.path.join(project_dir, "results", "nsga2-output.csv")
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
    final_population = nsga2.run(generations=generations, crossover_prob=crossover_prob, mutation_prob=mutation_prob)
    print(f"Final population: {len(final_population)} solutions")
    print(f"Final Pareto front size: {nsga2.pareto_front_sizes[-1]}")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    constructor.export_population(final_population, output_file)
    print(f"Results exported to {output_file}")
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
