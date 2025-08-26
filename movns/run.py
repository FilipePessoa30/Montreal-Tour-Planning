
import os
import sys
import time
import argparse
from typing import List, Dict, Tuple, Set, Optional, Any
from models import Solution

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from movns.constructor import MOVNSConstructor
from movns.movns import MOVNS

def run_movns(attractions_file: str, hotels_file: str, matrices_path: str,
             solution_count: int = 100, iterations: int = 100, no_improv_stop: int = 20,
             output_dir: str = "results"):
    print("Montreal Tour Planning with MOVNS")
    start_time = time.time()
    
    print("\n1. Initializing MOVNS Constructor")
    constructor = MOVNSConstructor(attractions_file, hotels_file, matrices_path)
    
    print("\n2. Setting up MOVNS Algorithm")
    movns = MOVNS(constructor, solution_count=solution_count, archive_max=30)
    
    print("\n3. Generating Initial Population")
    initial_population = movns.initialize_population()
    init_time = time.time() - start_time
    print(f"   - Initial population generated in {init_time:.2f} seconds")
    print(f"   - Initial Pareto set size: {len(initial_population)}")
    
    initial_file = os.path.join(output_dir, "movns-initial-population.csv")
    os.makedirs(os.path.dirname(initial_file), exist_ok=True)
    export_solutions(initial_population, initial_file)
    print(f"   - Initial population exported to {initial_file}")
    
    print("\n4. Running MOVNS Algorithm")
    final_population = movns.run(max_iterations=iterations, max_no_improvement=no_improv_stop)
    run_time = time.time() - start_time
    print(f"   - MOVNS completed in {run_time:.2f} seconds")
    print(f"   - Final Pareto set size: {len(final_population)}")
    
    pareto_file = os.path.join(output_dir, "movns-pareto-set.csv")
    metrics_file = os.path.join(output_dir, "movns-metrics.csv")
    movns.export_results(pareto_file, metrics_file)
    print(f"\n5. Results saved to:")
    print(f"   - Pareto set: {pareto_file}")
    print(f"   - Metrics: {metrics_file}")
    
    print_objective_statistics(final_population)
    
    return final_population

def export_solutions(solutions: List[Solution], output_file: str) -> None:
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w', newline='', encoding='utf-8') as file:
            file.write("Solution;Hotel;HotelRating;HotelPrice;TotalAttractions;TotalQuality;TotalTime;TotalCost;"
                      "Day1Attractions;Day1Neighborhoods;Day1Time;Day1Cost;Day2Attractions;Day2Neighborhoods;"
                      "Day2Time;Day2Cost;Day1Sequence;Day1TransportModes;Day2Sequence;Day2TransportModes\n")
            
            for i, solution in enumerate(solutions):
                try:
                    solution.objectives = solution.calculate_objectives()
                    
                    hotel = solution.hotel
                    day1 = solution.day1_route
                    day2 = solution.day2_route
                    objectives = solution.get_objectives()
                    
                    from models import TransportMode
                    day1_modes = []
                    day1_attractions = day1.get_attractions()
                    day1_transport_modes = day1.get_transport_modes()
                    
                    for j in range(len(day1_transport_modes)):
                        day1_modes.append(TransportMode.get_mode_string(day1_transport_modes[j]))
                    
                    day2_modes = []
                    day2_attractions = day2.get_attractions()
                    day2_transport_modes = day2.get_transport_modes()
                    
                    for j in range(len(day2_transport_modes)):
                        day2_modes.append(TransportMode.get_mode_string(day2_transport_modes[j]))
                    
                    file.write(f"{i + 1};")
                    file.write(f"{hotel.name};")
                    file.write(f"{hotel.rating:.1f};")
                    file.write(f"{hotel.price:.2f};")
                    file.write(f"{objectives[0]:.0f};")
                    file.write(f"{objectives[1]:.1f};")
                    file.write(f"{objectives[2]:.1f};")
                    file.write(f"{objectives[3]:.2f};")
                    
                    file.write(f"{day1.get_num_attractions()};")
                    file.write(f"{len(day1.get_neighborhoods())};")
                    file.write(f"{day1.get_total_time():.1f};")
                    file.write(f"{day1.get_total_cost():.2f};")
                    
                    file.write(f"{day2.get_num_attractions()};")
                    file.write(f"{len(day2.get_neighborhoods())};")
                    file.write(f"{day2.get_total_time():.1f};")
                    file.write(f"{day2.get_total_cost():.2f};")
                    
                    file.write("|".join(attr.name for attr in day1.get_attractions()) + ";")
                    file.write("|".join(day1_modes) + ";")
                    file.write("|".join(attr.name for attr in day2.get_attractions()) + ";")
                    file.write("|".join(day2_modes) + "\n")
                except Exception as e:
                    print(f"Error exporting solution {i+1}: {str(e)}")
                    continue
        
        print(f"Exported {len(solutions)} solutions to {output_file}")
    except Exception as e:
        print(f"Error exporting solutions: {str(e)}")

def print_objective_statistics(solutions: List[Solution]) -> None:
    if not solutions:
        print("\nNo solutions to analyze.")
        return
    
    print("\nObjective Statistics:")
    
    attractions = [s.get_objectives()[0] for s in solutions]
    quality = [s.get_objectives()[1] for s in solutions]
    time_values = [s.get_objectives()[2] for s in solutions]
    cost = [s.get_objectives()[3] for s in solutions]
    
    print(f"F1 - Attractions: Min = {min(attractions):.0f}, Max = {max(attractions):.0f}, " +
         f"Avg = {sum(attractions) / len(attractions):.2f}")
    
    print(f"F2 - Quality: Min = {min(quality):.1f}, Max = {max(quality):.1f}, " +
         f"Avg = {sum(quality) / len(quality):.2f}")
    
    print(f"F3 - Time (min): Min = {min(time_values):.1f}, Max = {max(time_values):.1f}, " +
         f"Avg = {sum(time_values) / len(time_values):.2f}")
    
    print(f"F4 - Cost (CA$): Min = {min(cost):.2f}, Max = {max(cost):.2f}, " +
         f"Avg = {sum(cost) / len(cost):.2f}")
    
    best_attraction_solution = max(solutions, key=lambda s: s.get_objectives()[0])
    best_quality_solution = max(solutions, key=lambda s: s.get_objectives()[1])
    best_time_solution = min(solutions, key=lambda s: s.get_objectives()[2])
    best_cost_solution = min(solutions, key=lambda s: s.get_objectives()[3])
    
    print("\nExtreme Solutions:")
    
    print("\nMaximum Attractions Solution:")
    obj = best_attraction_solution.get_objectives()
    print(f"  Hotel: {best_attraction_solution.hotel.name}")
    print(f"  Objectives: F1={obj[0]:.0f}, F2={obj[1]:.1f}, F3={obj[2]:.1f}, F4={obj[3]:.2f}")
    print(f"  Day 1: {len(best_attraction_solution.day1_route.get_attractions())} attractions")
    print(f"  Day 2: {len(best_attraction_solution.day2_route.get_attractions())} attractions")
    
    print("\nMaximum Quality Solution:")
    obj = best_quality_solution.get_objectives()
    print(f"  Hotel: {best_quality_solution.hotel.name}")
    print(f"  Objectives: F1={obj[0]:.0f}, F2={obj[1]:.1f}, F3={obj[2]:.1f}, F4={obj[3]:.2f}")
    print(f"  Day 1: {len(best_quality_solution.day1_route.get_attractions())} attractions")
    print(f"  Day 2: {len(best_quality_solution.day2_route.get_attractions())} attractions")
    
    print("\nMinimum Time Solution:")
    obj = best_time_solution.get_objectives()
    print(f"  Hotel: {best_time_solution.hotel.name}")
    print(f"  Objectives: F1={obj[0]:.0f}, F2={obj[1]:.1f}, F3={obj[2]:.1f}, F4={obj[3]:.2f}")
    print(f"  Day 1: {len(best_time_solution.day1_route.get_attractions())} attractions")
    print(f"  Day 2: {len(best_time_solution.day2_route.get_attractions())} attractions")
    
    print("\nMinimum Cost Solution:")
    obj = best_cost_solution.get_objectives()
    print(f"  Hotel: {best_cost_solution.hotel.name}")
    print(f"  Objectives: F1={obj[0]:.0f}, F2={obj[1]:.1f}, F3={obj[2]:.1f}, F4={obj[3]:.2f}")
    print(f"  Day 1: {len(best_cost_solution.day1_route.get_attractions())} attractions")
    print(f"  Day 2: {len(best_cost_solution.day2_route.get_attractions())} attractions")
    
    compromise_solutions = []
    
    min_attr = min(attractions)
    max_attr = max(attractions)
    range_attr = max_attr - min_attr
    
    min_qual = min(quality)
    max_qual = max(quality)
    range_qual = max_qual - min_qual
    
    min_time = min(time_values)
    max_time = max(time_values)
    range_time = max_time - min_time
    
    min_cost = min(cost)
    max_cost = max(cost)
    range_cost = max_cost - min_cost
    
    for s in solutions:
        obj = s.get_objectives()
        norm_attr = (obj[0] - min_attr) / range_attr if range_attr > 0 else 0
        norm_qual = (obj[1] - min_qual) / range_qual if range_qual > 0 else 0
        
        norm_time = 1 - ((obj[2] - min_time) / range_time if range_time > 0 else 0)
        norm_cost = 1 - ((obj[3] - min_cost) / range_cost if range_cost > 0 else 0)
        
        score = (norm_attr + norm_qual + norm_time + norm_cost) / 4
        
        compromise_solutions.append((s, score))
    
    compromise_solutions.sort(key=lambda x: x[1], reverse=True)
    best_compromise = compromise_solutions[0][0]
    
    print("\nBest Compromise Solution:")
    obj = best_compromise.get_objectives()
    print(f"  Hotel: {best_compromise.hotel.name}")
    print(f"  Objectives: F1={obj[0]:.0f}, F2={obj[1]:.1f}, F3={obj[2]:.1f}, F4={obj[3]:.2f}")
    print(f"  Day 1: {len(best_compromise.day1_route.get_attractions())} attractions")
    print(f"  Day 2: {len(best_compromise.day2_route.get_attractions())} attractions")
    print(f"  Score: {compromise_solutions[0][1]:.4f}")

def main():
    parser = argparse.ArgumentParser(description="Run MOVNS for Montreal Tour Planning")
    parser.add_argument("--attractions", "-a", default="places/attractions.csv",
                        help="Path to attractions CSV file")
    parser.add_argument("--hotels", "-H", default="places/hotels.csv",
                        help="Path to hotels CSV file")
    parser.add_argument("--matrices", "-m", default="results",
                        help="Path to transport matrices directory")
    parser.add_argument("--solutions", "-s", type=int, default=20,
                        help="Number of solutions in initial population")
    parser.add_argument("--iterations", "-i", type=int, default=50,
                        help="Maximum iterations for MOVNS")
    parser.add_argument("--no-improvement", "-n", type=int, default=20,
                        help="Stop after this many iterations without improvement")
    parser.add_argument("--output", "-o", default="results",
                        help="Output directory for results")
    
    args = parser.parse_args()
    
    run_movns(
        attractions_file=args.attractions,
        hotels_file=args.hotels,
        matrices_path=args.matrices,
        solution_count=args.solutions,
        iterations=args.iterations,
        no_improv_stop=args.no_improvement,
        output_dir=args.output
    )

if __name__ == "__main__":
    main()