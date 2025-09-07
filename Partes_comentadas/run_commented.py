# -*- coding: utf-8 -*-
"""
Versão comentada linha a linha de movns/run.py.
Objetivo: documentar cada passo do pipeline de execução (construção, execução, exportação e estatísticas).
A lógica foi preservada; apenas comentários foram adicionados.
"""

import os  # Operações com caminhos e diretórios
import sys  # Acesso a argv, path
import time  # Medição de tempo
import argparse  # Parser de argumentos CLI
from typing import List, Dict, Tuple, Set, Optional, Any  # Tipagem opcional
from models import Solution  # Tipo Solution para anotações e exportação

# Garante que o pacote raiz esteja no sys.path para imports relativos funcionarem ao executar diretamente
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from movns.constructor import MOVNSConstructor  # Construtor da população inicial e utilidades
from movns.movns import MOVNS  # Algoritmo MOVNS propriamente dito


def run_movns(attractions_file: str, hotels_file: str, matrices_path: str,
             solution_count: int = 100, iterations: int = 100, no_improv_stop: int = 20,
             output_dir: str = "results"):
    print("Montreal Tour Planning with MOVNS")  # Título informativo
    start_time = time.time()  # Marca início para medir tempos

    print("\n1. Initializing MOVNS Constructor")  # Etapa 1
    constructor = MOVNSConstructor(attractions_file, hotels_file, matrices_path)  # Carrega dados e prepara estruturas

    print("\n2. Setting up MOVNS Algorithm")  # Etapa 2
    movns = MOVNS(constructor, solution_count=solution_count, archive_max=30)  # Instancia algoritmo com limites

    print("\n3. Generating Initial Population")  # Etapa 3
    initial_population = movns.initialize_population()  # Gera e filtra frente inicial
    init_time = time.time() - start_time  # Tempo gasto até aqui
    print(f"   - Initial population generated in {init_time:.2f} seconds")  # Log tempo
    print(f"   - Initial Pareto set size: {len(initial_population)}")  # Tamanho da frente

    initial_file = os.path.join(output_dir, "movns-initial-population.csv")  # Caminho do CSV inicial
    os.makedirs(os.path.dirname(initial_file), exist_ok=True)  # Garante dir de saída
    export_solutions(initial_population, initial_file)  # Exporta população inicial
    print(f"   - Initial population exported to {initial_file}")  # Log

    print("\n4. Running MOVNS Algorithm")  # Etapa 4
    final_population = movns.run(max_iterations=iterations, max_no_improvement=no_improv_stop)  # Executa VNS multiobjetivo
    run_time = time.time() - start_time  # Tempo total
    print(f"   - MOVNS completed in {run_time:.2f} seconds")  # Log
    print(f"   - Final Pareto set size: {len(final_population)}")  # Tamanho final da frente

    pareto_file = os.path.join(output_dir, "movns-pareto-set.csv")  # Caminho CSV Pareto final
    metrics_file = os.path.join(output_dir, "movns-metrics.csv")  # Caminho CSV de métricas por iteração
    movns.export_results(pareto_file, metrics_file)  # Exporta usando método do algoritmo
    print(f"\n5. Results saved to:")  # Resumo de saídas
    print(f"   - Pareto set: {pareto_file}")
    print(f"   - Metrics: {metrics_file}")

    print_objective_statistics(final_population)  # Exibe estatísticas agregadas e extremos

    return final_population  # Retorna população final


def export_solutions(solutions: List[Solution], output_file: str) -> None:  # Exporta detalhes da população para CSV
    try:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)  # Garante diretório

        with open(output_file, 'w', newline='', encoding='utf-8') as file:  # Abre arquivo CSV
            file.write("Solution;Hotel;HotelRating;HotelPrice;TotalAttractions;TotalQuality;TotalTime;TotalCost;"
                      "Day1Attractions;Day1Neighborhoods;Day1Time;Day1Cost;Day2Attractions;Day2Neighborhoods;"
                      "Day2Time;Day2Cost;Day1Sequence;Day1TransportModes;Day2Sequence;Day2TransportModes\n")  # Cabeçalho

            for i, solution in enumerate(solutions):  # Para cada solução
                try:
                    solution.objectives = solution.calculate_objectives()  # Garante objetivos atualizados

                    hotel = solution.hotel  # Hotel
                    day1 = solution.day1_route  # Rota dia 1
                    day2 = solution.day2_route  # Rota dia 2
                    objectives = solution.get_objectives()  # Vetor [F1..F4]

                    from models import TransportMode  # Enum de modos
                    day1_modes = []  # Lista textual de modos dia 1
                    day1_attractions = day1.get_attractions()  # Lista de atrações dia 1 (não usada diretamente abaixo)
                    day1_transport_modes = day1.get_transport_modes()  # Modos de transporte dia 1

                    for j in range(len(day1_transport_modes)):  # Converte enum -> string
                        day1_modes.append(TransportMode.get_mode_string(day1_transport_modes[j]))

                    day2_modes = []  # Lista textual de modos dia 2
                    day2_attractions = day2.get_attractions()  # Lista de atrações dia 2
                    day2_transport_modes = day2.get_transport_modes()  # Modos de transporte dia 2

                    for j in range(len(day2_transport_modes)):
                        day2_modes.append(TransportMode.get_mode_string(day2_transport_modes[j]))

                    file.write(f"{i + 1};")  # Número da solução
                    file.write(f"{hotel.name};")  # Nome do hotel
                    file.write(f"{hotel.rating:.1f};")  # Nota do hotel
                    file.write(f"{hotel.price:.2f};")  # Preço do hotel
                    file.write(f"{objectives[0]:.0f};")  # F1
                    file.write(f"{objectives[1]:.1f};")  # F2
                    file.write(f"{objectives[2]:.1f};")  # F3
                    file.write(f"{objectives[3]:.2f};")  # F4

                    file.write(f"{day1.get_num_attractions()};")  # Nº atrações dia 1
                    file.write(f"{len(day1.get_neighborhoods())};")  # Nº bairros dia 1
                    file.write(f"{day1.get_total_time():.1f};")  # Tempo total dia 1
                    file.write(f"{day1.get_total_cost():.2f};")  # Custo total dia 1

                    file.write(f"{day2.get_num_attractions()};")  # Nº atrações dia 2
                    file.write(f"{len(day2.get_neighborhoods())};")  # Nº bairros dia 2
                    file.write(f"{day2.get_total_time():.1f};")  # Tempo total dia 2
                    file.write(f"{day2.get_total_cost():.2f};")  # Custo total dia 2

                    file.write("|".join(attr.name for attr in day1.get_attractions()) + ";")  # Sequência atrações dia 1
                    file.write("|".join(day1_modes) + ";")  # Modos concatenados dia 1
                    file.write("|".join(attr.name for attr in day2.get_attractions()) + ";")  # Sequência atrações dia 2
                    file.write("|".join(day2_modes) + "\n")  # Modos concatenados dia 2 + quebra
                except Exception as e:  # Em caso de erro numa solução
                    print(f"Error exporting solution {i+1}: {str(e)}")  # Loga e continua
                    continue

        print(f"Exported {len(solutions)} solutions to {output_file}")  # Mensagem de sucesso
    except Exception as e:  # Falha geral de IO
        print(f"Error exporting solutions: {str(e)}")  # Loga erro


def print_objective_statistics(solutions: List[Solution]) -> None:  # Mostra métricas agregadas no console
    if not solutions:  # Sem soluções
        print("\nNo solutions to analyze.")
        return

    print("\nObjective Statistics:")  # Título

    attractions = [s.get_objectives()[0] for s in solutions]  # Lista F1
    quality = [s.get_objectives()[1] for s in solutions]  # Lista F2
    time_values = [s.get_objectives()[2] for s in solutions]  # Lista F3
    cost = [s.get_objectives()[3] for s in solutions]  # Lista F4

    print(f"F1 - Attractions: Min = {min(attractions):.0f}, Max = {max(attractions):.0f}, " +
          f"Avg = {sum(attractions) / len(attractions):.2f}")  # Estatística F1

    print(f"F2 - Quality: Min = {min(quality):.1f}, Max = {max(quality):.1f}, " +
          f"Avg = {sum(quality) / len(quality):.2f}")  # Estatística F2

    print(f"F3 - Time (min): Min = {min(time_values):.1f}, Max = {max(time_values):.1f}, " +
          f"Avg = {sum(time_values) / len(time_values):.2f}")  # Estatística F3

    print(f"F4 - Cost (CA$): Min = {min(cost):.2f}, Max = {max(cost):.2f}, " +
          f"Avg = {sum(cost) / len(cost):.2f}")  # Estatística F4

    best_attraction_solution = max(solutions, key=lambda s: s.get_objectives()[0])  # Maior F1
    best_quality_solution = max(solutions, key=lambda s: s.get_objectives()[1])  # Maior F2
    best_time_solution = min(solutions, key=lambda s: s.get_objectives()[2])  # Menor F3
    best_cost_solution = min(solutions, key=lambda s: s.get_objectives()[3])  # Menor F4

    print("\nExtreme Solutions:")  # Título

    print("\nMaximum Attractions Solution:")  # Solução com mais atrações
    obj = best_attraction_solution.get_objectives()
    print(f"  Hotel: {best_attraction_solution.hotel.name}")
    print(f"  Objectives: F1={obj[0]:.0f}, F2={obj[1]:.1f}, F3={obj[2]:.1f}, F4={obj[3]:.2f}")
    print(f"  Day 1: {len(best_attraction_solution.day1_route.get_attractions())} attractions")
    print(f"  Day 2: {len(best_attraction_solution.day2_route.get_attractions())} attractions")

    print("\nMaximum Quality Solution:")  # Solução com maior qualidade
    obj = best_quality_solution.get_objectives()
    print(f"  Hotel: {best_quality_solution.hotel.name}")
    print(f"  Objectives: F1={obj[0]:.0f}, F2={obj[1]:.1f}, F3={obj[2]:.1f}, F4={obj[3]:.2f}")
    print(f"  Day 1: {len(best_quality_solution.day1_route.get_attractions())} attractions")
    print(f"  Day 2: {len(best_quality_solution.day2_route.get_attractions())} attractions")

    print("\nMinimum Time Solution:")  # Solução mais rápida
    obj = best_time_solution.get_objectives()
    print(f"  Hotel: {best_time_solution.hotel.name}")
    print(f"  Objectives: F1={obj[0]:.0f}, F2={obj[1]:.1f}, F3={obj[2]:.1f}, F4={obj[3]:.2f}")
    print(f"  Day 1: {len(best_time_solution.day1_route.get_attractions())} attractions")
    print(f"  Day 2: {len(best_time_solution.day2_route.get_attractions())} attractions")

    print("\nMinimum Cost Solution:")  # Solução mais barata
    obj = best_cost_solution.get_objectives()
    print(f"  Hotel: {best_cost_solution.hotel.name}")
    print(f"  Objectives: F1={obj[0]:.0f}, F2={obj[1]:.1f}, F3={obj[2]:.1f}, F4={obj[3]:.2f}")
    print(f"  Day 1: {len(best_cost_solution.day1_route.get_attractions())} attractions")
    print(f"  Day 2: {len(best_cost_solution.day2_route.get_attractions())} attractions")

    compromise_solutions = []  # Lista de (solução, escore) pelo método simples de normalização linear

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

    for s in solutions:  # Calcula um escore simples (média das normalizações)
        obj = s.get_objectives()
        norm_attr = (obj[0] - min_attr) / range_attr if range_attr > 0 else 0  # Maior é melhor
        norm_qual = (obj[1] - min_qual) / range_qual if range_qual > 0 else 0  # Maior é melhor

        norm_time = 1 - ((obj[2] - min_time) / range_time if range_time > 0 else 0)  # Menor é melhor
        norm_cost = 1 - ((obj[3] - min_cost) / range_cost if range_cost > 0 else 0)  # Menor é melhor

        score = (norm_attr + norm_qual + norm_time + norm_cost) / 4  # Média simples

        compromise_solutions.append((s, score))  # Guarda

    compromise_solutions.sort(key=lambda x: x[1], reverse=True)  # Ordena por escore desc
    best_compromise = compromise_solutions[0][0]  # Melhor compromisso

    print("\nBest Compromise Solution:")  # Exibe melhor compromisso
    obj = best_compromise.get_objectives()
    print(f"  Hotel: {best_compromise.hotel.name}")
    print(f"  Objectives: F1={obj[0]:.0f}, F2={obj[1]:.1f}, F3={obj[2]:.1f}, F4={obj[3]:.2f}")
    print(f"  Day 1: {len(best_compromise.day1_route.get_attractions())} attractions")
    print(f"  Day 2: {len(best_compromise.day2_route.get_attractions())} attractions")
    print(f"  Score: {compromise_solutions[0][1]:.4f}")


def main():  # CLI principal
    parser = argparse.ArgumentParser(description="Run MOVNS for Montreal Tour Planning")  # Cria parser
    parser.add_argument("--attractions", "-a", default="places/attractions.csv",
                        help="Path to attractions CSV file")  # Caminho das atrações
    parser.add_argument("--hotels", "-H", default="places/hotels.csv",
                        help="Path to hotels CSV file")  # Caminho dos hotéis
    parser.add_argument("--matrices", "-m", default="results",
                        help="Path to transport matrices directory")  # Caminho das matrizes
    parser.add_argument("--solutions", "-s", type=int, default=20,
                        help="Number of solutions in initial population")  # Tamanho população
    parser.add_argument("--iterations", "-i", type=int, default=50,
                        help="Maximum iterations for MOVNS")  # Nº máximo de iterações
    parser.add_argument("--no-improvement", "-n", type=int, default=20,
                        help="Stop after this many iterations without improvement")  # Parada por estagnação
    parser.add_argument("--output", "-o", default="results",
                        help="Output directory for results")  # Diretório de saída

    args = parser.parse_args()  # Parseia argumentos

    run_movns(  # Chama pipeline com os argumentos coletados
        attractions_file=args.attractions,
        hotels_file=args.hotels,
        matrices_path=args.matrices,
        solution_count=args.solutions,
        iterations=args.iterations,
        no_improv_stop=args.no_improvement,
        output_dir=args.output
    )


if __name__ == "__main__":  # Ponto de entrada quando executado como script
    main()  # Invoca CLI
