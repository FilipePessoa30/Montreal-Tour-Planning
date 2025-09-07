"""
Ferramenta de verificação de soluções (comentada linha a linha).
Replica verify_solutions.py adicionando explicações detalhadas sem alterar a lógica.
"""

# Imports padrão
import os   # Caminhos e verificação de arquivos
import sys  # Saída/retorno de código
import csv  # (não usado diretamente; mantido por compatibilidade)
import time # Medição de tempo de execução
import pandas as pd  # (não usado diretamente; mantido por compatibilidade)
import argparse      # CLI
from typing import List, Dict, Tuple, Set, Optional, Any  # Tipagem

# Domínio e utilitários do projeto
from models import Solution, Hotel, DailyRoute, Attraction, TransportMode
from utils import Parser, Transport, normalize_string, Config, TransportMatrices


# Classe principal que realiza a verificação das soluções exportadas
class SolutionVerifier:
    
    def __init__(self, attractions_file: str, hotels_file: str, matrices_path: str):
        # Mensagem inicial para diagnóstico
        print("Initializing solution verifier...")
        
        # Carrega entidades de domínio a partir de CSVs
        self.attractions = Parser.load_attractions(attractions_file)
        self.hotels = Parser.load_hotels(hotels_file)
        
        # Índices por nome para consultas rápidas
        self.attraction_by_name = {attr.name: attr for attr in self.attractions}
        self.hotel_by_name = {hotel.name: hotel for hotel in self.hotels}
        
        # Carrega matrizes de transporte (tempos entre locais por modo)
        success = Parser.load_transport_matrices(matrices_path)
        if not success:
            # Interrompe se não conseguir carregar as matrizes
            raise RuntimeError("Failed to load transport matrices")
        
        # Logs de quantidade carregada
        print(f"Loaded {len(self.attractions)} attractions and {len(self.hotels)} hotels")
        print(f"Loaded {len(TransportMatrices.attraction_names)} locations from transport matrices")
    
    def verify_solution_file(self, solution_file: str, output_file: str = None) -> bool:
        # Título do processo atual
        print(f"\nVerifying solutions from: {solution_file}")
        
        try:
            # Lê o CSV de soluções para uma lista de dicionários
            solutions = self._parse_solution_file(solution_file)
            
            if not solutions:
                # Se não tiver registros, encerra com erro
                print("ERROR: No solutions found in the file")
                return False
            
            print(f"Found {len(solutions)} solutions to verify")
            
            # Acumula resultados individuais de verificação
            verification_results = []
            valid_count = 0
            error_count = 0
            
            # Processa cada solução
            for i, solution_data in enumerate(solutions):
                try:
                    # Mensagem de progresso em mesma linha
                    print(f"Verifying solution {i+1}/{len(solutions)}...", end="\r")
                    
                    # Verifica de fato a solução
                    result = self.verify_solution(solution_data)
                    
                    # Atualiza contadores
                    if result["is_valid"]:
                        valid_count += 1
                    else:
                        error_count += 1
                    
                    # Armazena resultado
                    verification_results.append(result)
                except Exception as e:
                    # Em caso de erro inesperado, registra e avança
                    print(f"\nERROR verifying solution {i+1}: {str(e)}")
                    error_count += 1
                    verification_results.append({
                        "solution_index": i + 1,
                        "is_valid": False,
                        "error": str(e),
                        "hotel_name": solution_data.get("Hotel", "Unknown"),
                        "reported_objectives": {
                            "attractions": 0,
                            "quality": 0,
                            "time": 0,
                            "cost": 0,
                        },
                        "calculated_objectives": {
                            "attractions": 0,
                            "quality": 0,
                            "time": 0,
                            "cost": 0,
                        },
                        "details": []
                    })
            
            # Resumo final
            print(f"\nVerification complete: {valid_count} valid, {error_count} invalid")
            
            # Se pedido, escreve arquivo de saída com os resultados
            if output_file:
                self._write_verification_results(verification_results, output_file)
                print(f"Verification results written to: {output_file}")
            
            # Estatísticas adicionais (apenas para válidas)
            if verification_results:
                self._print_objective_statistics(verification_results)
            
            # Retorna True se não houve inválidas
            return error_count == 0
            
        except Exception as e:
            # Dump de erro global
            print(f"ERROR during verification: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def verify_solution(self, solution_data: Dict) -> Dict:
        # Extrai identificadores básicos
        solution_index = solution_data.get("Solution", 0)
        hotel_name = solution_data.get("Hotel", "")
        
        # Esqueleto do resultado de verificação desta solução
        result = {
            "solution_index": solution_index,
            "is_valid": True,
            "hotel_name": hotel_name,
            "hotel_errors": [],
            "day1_errors": [],
            "day2_errors": [],
            "objective_errors": [],
            "reported_objectives": {
                "attractions": float(solution_data.get("TotalAttractions", 0)),
                "quality": float(solution_data.get("TotalQuality", 0)),
                "time": float(solution_data.get("TotalTime", 0)),
                "cost": float(solution_data.get("TotalCost", 0)),
            },
            "calculated_objectives": {
                "attractions": 0,
                "quality": 0,
                "time": 0,
                "cost": 0,
            },
            "details": []
        }
        
        # Busca o hotel correspondente
        hotel = self.hotel_by_name.get(hotel_name)
        if not hotel:
            # Se não existir, marca inválida e retorna
            result["is_valid"] = False
            result["hotel_errors"].append(f"Hotel '{hotel_name}' not found")
            return result
        
        # Sequência/modes do Dia 1 (Sábado)
        day1_attractions = solution_data.get("Day1Sequence", "").split("|")
        day1_modes = solution_data.get("Day1TransportModes", "").split("|")
        
        # Normaliza listas vazias
        if day1_attractions == [""]:
            day1_attractions = []
        if day1_modes == [""]:
            day1_modes = []
            
        # Garante comprimento de modes = #atracoes + 1 (inclui retorno)
        while len(day1_modes) < len(day1_attractions) + 1 and day1_attractions:
            day1_modes.append("Car")
        
        # Verifica rota do Dia 1
        day1_result = self._verify_day_route(
            day1_attractions, 
            day1_modes, 
            hotel_name, 
            is_saturday=True,
            solution_data=solution_data
        )
        
        # Propaga erros se houver
        if not day1_result["is_valid"]:
            result["is_valid"] = False
            result["day1_errors"] = day1_result["errors"]
        
        # Sequência/modes do Dia 2 (Domingo)
        day2_attractions = solution_data.get("Day2Sequence", "").split("|")
        day2_modes = solution_data.get("Day2TransportModes", "").split("|")
        
        if day2_attractions == [""]:
            day2_attractions = []
        if day2_modes == [""]:
            day2_modes = []
            
        while len(day2_modes) < len(day2_attractions) + 1 and day2_attractions:
            day2_modes.append("Car")
        
        # Verifica rota do Dia 2
        day2_result = self._verify_day_route(
            day2_attractions, 
            day2_modes, 
            hotel_name, 
            is_saturday=False,
            solution_data=solution_data
        )
        
        if not day2_result["is_valid"]:
            result["is_valid"] = False
            result["day2_errors"] = day2_result["errors"]
        
        # Checa sobreposição de atrações entre os dois dias (não permitido)
        filtered_day1_attractions = [attr for attr in day1_attractions if attr]
        filtered_day2_attractions = [attr for attr in day2_attractions if attr]
        
        day1_attr_set = set(filtered_day1_attractions)
        day2_attr_set = set(filtered_day2_attractions)
        overlap = day1_attr_set.intersection(day2_attr_set)
        
        if overlap:
            result["is_valid"] = False
            result["day1_errors"].append(f"Overlapping attractions with day 2: {', '.join(overlap)}")
        
        # Recalcula objetivos e compara com reportados
        if hotel:
            # Atrações totais
            result["calculated_objectives"]["attractions"] = len(filtered_day1_attractions) + len(filtered_day2_attractions)
            
            # Qualidade = 2x nota do hotel + soma das notas das atrações
            quality_value = hotel.rating * 2
            
            for attr_name in filtered_day1_attractions:
                attr = self.attraction_by_name.get(attr_name)
                if attr:
                    quality_value += attr.rating
            
            for attr_name in filtered_day2_attractions:
                attr = self.attraction_by_name.get(attr_name)
                if attr:
                    quality_value += attr.rating
            
            result["calculated_objectives"]["quality"] = quality_value
            
            # Tempo total (min) = tempos retornados pelo verificador diário
            result["calculated_objectives"]["time"] = day1_result.get("total_time", 0) + day2_result.get("total_time", 0)
            
            # Custo total = preço do hotel + custos de transportes + custos de atrações
            cost_value = hotel.price
            
            cost_value += day1_result.get("total_cost", 0) + day2_result.get("total_cost", 0)
            
            result["calculated_objectives"]["cost"] = cost_value
            
            # Tolerância para comparações numéricas
            tolerance = 1.0

            try:
                # Atrações: compara inteiro com tolerância (para robustez)
                reported_attractions = float(result["reported_objectives"]["attractions"])
                calculated_attractions = result["calculated_objectives"]["attractions"]
                if abs(reported_attractions - calculated_attractions) > tolerance:
                    result["is_valid"] = False
                    result["objective_errors"].append(
                        f"Reported attractions ({reported_attractions}) " +
                        f"does not match calculated ({calculated_attractions})"
                    )

                # Qualidade: compara soma de notas
                reported_quality = float(result["reported_objectives"]["quality"])
                calculated_quality = result["calculated_objectives"]["quality"]
                if abs(reported_quality - calculated_quality) > tolerance:
                    result["is_valid"] = False
                    result["objective_errors"].append(
                        f"Reported quality ({reported_quality}) " +
                        f"does not match calculated ({calculated_quality:.1f})"
                    )

                # Tempo: permite diferença absoluta e percentual
                reported_time = float(result["reported_objectives"]["time"])
                calculated_time = result["calculated_objectives"]["time"]
                time_difference = abs(reported_time - calculated_time)
                time_pct_difference = time_difference / calculated_time if calculated_time > 0 else 0

                if time_difference > tolerance * 100 and time_pct_difference > 0.15:
                    result["is_valid"] = False
                    result["objective_errors"].append(
                        f"Reported time ({reported_time}) " +
                        f"does not match calculated ({calculated_time:.1f})" +
                        f" - Difference: {time_difference:.1f} min ({time_pct_difference*100:.1f}%)"
                    )
                
                # Custo: permite diferença absoluta e percentual
                reported_cost = float(result["reported_objectives"]["cost"])
                calculated_cost = result["calculated_objectives"]["cost"]
                cost_difference = abs(reported_cost - calculated_cost)
                cost_pct_difference = cost_difference / calculated_cost if calculated_cost > 0 else 0

                if cost_difference > tolerance * 30 and cost_pct_difference > 0.10:
                    result["is_valid"] = False
                    result["objective_errors"].append(
                        f"Reported cost ({reported_cost}) " +
                        f"does not match calculated ({calculated_cost:.2f})" +
                        f" - Difference: ${cost_difference:.2f} ({cost_pct_difference*100:.1f}%)"
                    )
            except (ValueError, TypeError) as e:
                # Se os dados reportados não forem numéricos, marca como erro
                result["is_valid"] = False
                result["objective_errors"].append(f"Error comparing objectives: {str(e)}")
        
        # Monta um sumário textual amigável
        result["details"] = [
            f"Hotel: {hotel_name} (Price: {hotel.price if hotel else 'N/A'}, Rating: {hotel.rating if hotel else 'N/A'})",
            f"Day 1 (Saturday): {len(filtered_day1_attractions)} attractions, Time: {day1_result.get('total_time', 0):.1f} min, Cost: CA$ {day1_result.get('total_cost', 0):.2f}",
            f"Day 2 (Sunday): {len(filtered_day2_attractions)} attractions, Time: {day2_result.get('total_time', 0):.1f} min, Cost: CA$ {day2_result.get('total_cost', 0):.2f}",
            f"Total: {result['calculated_objectives']['attractions']} attractions, " +
            f"Quality: {result['calculated_objectives']['quality']:.1f}, " +
            f"Time: {result['calculated_objectives']['time']:.1f} min, " +
            f"Cost: CA$ {result['calculated_objectives']['cost']:.2f}"
        ]
        
        # Retorna estrutura desta verificação
        return result
    
    def _verify_day_route(self, attractions: List[str], transport_modes: List[str], 
                        hotel_name: str, is_saturday: bool, solution_data: Dict) -> Dict:
        # Estrutura acumuladora dos dados do dia
        result = {
            "is_valid": True,
            "errors": [],
            "total_time": 0.0,
            "total_cost": 0.0,
            "total_visit_time": 0.0,
            "total_travel_time": 0.0,
            "total_wait_time": 0.0,
            "details": []
        }
        
        # Recupera hotel
        hotel = self.hotel_by_name.get(hotel_name)
        if not hotel:
            result["is_valid"] = False
            result["errors"].append(f"Hotel '{hotel_name}' not found")
            return result
        
        # Se não há atrações, nada a validar
        if not attractions or attractions == [""]:
            return result
        
        # Detecta duplicatas na sequência
        attraction_count = {}
        for attr_name in attractions:
            if not attr_name:
                continue
            if attr_name in attraction_count:
                attraction_count[attr_name] += 1
            else:
                attraction_count[attr_name] = 1
        
        duplicates = [name for name, count in attraction_count.items() if count > 1]
        if duplicates:
            result["is_valid"] = False
            result["errors"].append(f"Duplicate attractions found in {'Saturday' if is_saturday else 'Sunday'} route: {', '.join(duplicates)}")
        
        # Confere existência e abertura no dia
        all_attractions_valid = True
        for i, attr_name in enumerate(attractions):
            if not attr_name:
                continue
                
            attraction = self.attraction_by_name.get(attr_name)
            
            if not attraction:
                result["is_valid"] = False
                result["errors"].append(f"Attraction '{attr_name}' not found")
                all_attractions_valid = False
                continue
            
            if not attraction.is_open_on_day(is_saturday):
                result["is_valid"] = False
                result["errors"].append(f"Attraction '{attr_name}' is not open on {'Saturday' if is_saturday else 'Sunday'}")
                all_attractions_valid = False
        
        if not all_attractions_valid:
            return result
        
        # Converte strings de modos em enums; coleta erros de modo
        mode_errors = False
        transport_mode_objects = []
        
        for i, mode_name in enumerate(transport_modes):
            if not mode_name:
                continue
                
            try:
                if mode_name == "Walking":
                    mode = TransportMode.WALK
                elif mode_name == "Subway":
                    mode = TransportMode.SUBWAY_WALK
                elif mode_name == "Bus":
                    mode = TransportMode.BUS_WALK
                elif mode_name == "Car":
                    mode = TransportMode.CAR
                else:
                    result["is_valid"] = False
                    result["errors"].append(f"Invalid transport mode: '{mode_name}'")
                    mode_errors = True
                    continue
                
                transport_mode_objects.append(mode)
            except Exception as e:
                result["is_valid"] = False
                result["errors"].append(f"Error parsing transport mode '{mode_name}': {str(e)}")
                mode_errors = True
        
        if mode_errors:
            return result
        
        # Devem existir (#atracoes + 1) modos (incluindo retorno ao hotel)
        if len(transport_mode_objects) < len(attractions) + 1:
            result["is_valid"] = False
            result["errors"].append(
                f"Not enough transport modes: got {len(transport_mode_objects)}, " +
                f"need {len(attractions) + 1} (including return to hotel)"
            )
            return result
        
        # Janela de operação do dia
        start_time = 8 * 60
        end_time = 20 * 60
        current_time = start_time
        
        # Primeiro deslocamento: hotel -> primeira atração
        first_attraction = self.attraction_by_name.get(attractions[0])
        first_mode = transport_mode_objects[0]
        
        travel_time = Transport.get_travel_time(hotel_name, first_attraction.name, first_mode)
        
        if travel_time < 0:
            result["is_valid"] = False
            result["errors"].append(
                f"Invalid travel from hotel to first attraction '{first_attraction.name}' " +
                f"with mode {first_mode.name}"
            )
            return result
        
        current_time += travel_time
        result["total_travel_time"] += travel_time
        
        if first_mode == TransportMode.CAR:
            result["total_cost"] += travel_time * Config.CAR_COST_PER_MINUTE
        
        # Itera atrações do dia
        for i, attr_name in enumerate(attractions):
            attraction = self.attraction_by_name.get(attr_name)
            
            # Recupera janela de abertura/fechamento para o dia da semana
            opening_time = attraction.get_opening_time(is_saturday)
            closing_time = attraction.get_closing_time(is_saturday)
            
            # Espera se chegou antes de abrir
            wait_time = 0
            if current_time < opening_time:
                wait_time = opening_time - current_time
                current_time = opening_time
            
            result["total_wait_time"] += wait_time
            
            # Se já chegou após fechar, invalida
            if current_time >= closing_time:
                result["is_valid"] = False
                result["errors"].append(
                    f"Arrived at attraction '{attr_name}' at {self._format_time(current_time)}, " +
                    f"but it closes at {self._format_time(closing_time)}"
                )
                break
            
            # Consome tempo de visita
            current_time += attraction.visit_time
            result["total_visit_time"] += attraction.visit_time
            
            # Soma custo da atração
            result["total_cost"] += attraction.cost
            
            # Se a visita extrapola o horário de fechamento, invalida
            if current_time > closing_time:
                result["is_valid"] = False
                result["errors"].append(
                    f"Visit to attraction '{attr_name}' extends beyond closing time " +
                    f"({self._format_time(current_time)} > {self._format_time(closing_time)})"
                )
                break
            
            # Deslocamento atração atual -> próxima (se houver)
            if i < len(attractions) - 1:
                next_attraction = self.attraction_by_name.get(attractions[i+1])
                next_mode = transport_mode_objects[i+1]
                
                travel_time = Transport.get_travel_time(attraction.name, next_attraction.name, next_mode)
                
                if travel_time < 0:
                    result["is_valid"] = False
                    result["errors"].append(
                        f"Invalid travel from '{attr_name}' to '{next_attraction.name}' " +
                        f"with mode {next_mode.name}"
                    )
                    break
                
                # Acumula tempo de deslocamento e custo (se CAR)
                current_time += travel_time
                result["total_travel_time"] += travel_time
                
                if next_mode == TransportMode.CAR:
                    result["total_cost"] += travel_time * Config.CAR_COST_PER_MINUTE
        
        # Retorno ao hotel (se tudo válido até aqui)
        if result["is_valid"] and attractions:
            last_attraction = self.attraction_by_name.get(attractions[-1])
            return_mode = transport_mode_objects[len(attractions)]
            
            travel_time = Transport.get_travel_time(last_attraction.name, hotel_name, return_mode)
            
            if travel_time < 0:
                result["is_valid"] = False
                result["errors"].append(
                    f"Invalid travel from last attraction '{last_attraction.name}' " +
                    f"back to hotel with mode {return_mode.name}"
                )
                return result
            
            current_time += travel_time
            result["total_travel_time"] += travel_time
            
            if return_mode == TransportMode.CAR:
                result["total_cost"] += travel_time * Config.CAR_COST_PER_MINUTE
            
            # Garante que não ultrapassou fim do dia
            if current_time > end_time:
                result["is_valid"] = False
                result["errors"].append(
                    f"Return to hotel extends beyond end of day " +
                    f"({self._format_time(current_time)} > {self._format_time(end_time)})"
                )
        
        # Tempo total do dia = deslocamento + visita + espera
        result["total_time"] = result["total_travel_time"] + result["total_visit_time"] + result["total_wait_time"]
        
        return result
    
    def _parse_solution_file(self, file_path: str) -> List[Dict]:
        # Lê um CSV simples separado por ponto e vírgula e retorna lista de dicts
        solutions = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                # Cabeçalho define os nomes das colunas
                header = file.readline().strip().split(';')
                
                # Cada linha vira um dicionário mapeando coluna->valor
                for i, line in enumerate(file):
                    try:
                        if not line.strip():
                            continue
                        
                        fields = line.strip().split(';')
                        
                        solution = {}
                        
                        for j, field in enumerate(fields):
                            if j < len(header):
                                solution[header[j]] = field
                        
                        solutions.append(solution)
                    except Exception as e:
                        print(f"Error parsing solution on line {i+2}: {str(e)}")
        except Exception as e:
            print(f"Error reading solution file: {str(e)}")
        
        return solutions
    
    def _write_verification_results(self, results: List[Dict], output_file: str) -> None:
        # Grava um CSV resumindo a verificação por solução
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as file:
                # Cabeçalho do CSV de saída (separador ';')
                file.write("Solution;Hotel;IsValid;ReportedAttractions;CalculatedAttractions;ReportedQuality;"
                          "CalculatedQuality;ReportedTime;CalculatedTime;ReportedCost;CalculatedCost;Errors\n")
                
                for result in results:
                    try:
                        # Agrega todas as mensagens de erro em um único campo
                        all_errors = []
                        all_errors.extend(result.get("hotel_errors", []))
                        all_errors.extend(result.get("day1_errors", []))
                        all_errors.extend(result.get("day2_errors", []))
                        all_errors.extend(result.get("objective_errors", []))
                        
                        errors_str = " | ".join(all_errors).replace(";", ",")
                        
                        # Escreve colunas fixas
                        file.write(f"{result['solution_index']};")
                        file.write(f"{result['hotel_name']};")
                        file.write(f"{result['is_valid']};")
                        
                        reported_objectives = result.get("reported_objectives", {})
                        calculated_objectives = result.get("calculated_objectives", {})
                        
                        file.write(f"{reported_objectives.get('attractions', 0)};")
                        file.write(f"{calculated_objectives.get('attractions', 0)};")
                        
                        file.write(f"{reported_objectives.get('quality', 0)};")
                        file.write(f"{calculated_objectives.get('quality', 0):.1f};")
                        
                        file.write(f"{reported_objectives.get('time', 0)};")
                        file.write(f"{calculated_objectives.get('time', 0):.1f};")
                        
                        file.write(f"{reported_objectives.get('cost', 0)};")
                        file.write(f"{calculated_objectives.get('cost', 0):.2f};")
                        
                        file.write(f"{errors_str}\n")
                    except Exception as e:
                        print(f"Error writing result for solution {result.get('solution_index', 'Unknown')}: {str(e)}")
        except Exception as e:
            print(f"Error writing verification results: {str(e)}")
    
    def _print_objective_statistics(self, results: List[Dict]) -> None:
        # Imprime estatísticas básicas para soluções válidas
        valid_results = [r for r in results if r.get("is_valid", False)]
        
        if not valid_results:
            print("\nNo valid solutions to calculate statistics for.")
            return
        
        print("\nObjective Statistics for Valid Solutions:")
        
        attractions = [r.get("calculated_objectives", {}).get("attractions", 0) for r in valid_results]
        print(f"Attractions: Min = {min(attractions)}, Max = {max(attractions)}, "
             f"Avg = {sum(attractions) / len(attractions):.2f}")
        
        quality = [r.get("calculated_objectives", {}).get("quality", 0) for r in valid_results]
        print(f"Quality: Min = {min(quality):.1f}, Max = {max(quality):.1f}, "
             f"Avg = {sum(quality) / len(quality):.2f}")
        
        time_values = [r.get("calculated_objectives", {}).get("time", 0) for r in valid_results]
        print(f"Time (min): Min = {min(time_values):.1f}, Max = {max(time_values):.1f}, "
             f"Avg = {sum(time_values) / len(time_values):.2f}")
        
        cost = [r.get("calculated_objectives", {}).get("cost", 0) for r in valid_results]
        print(f"Cost (CA$): Min = {min(cost):.2f}, Max = {max(cost):.2f}, "
             f"Avg = {sum(cost) / len(cost):.2f}")
        
        print("\nTop 3 Solutions by Objective:")
        
        # Top 3 por número de atrações (maior é melhor)
        print("\nTop 3 by Attractions (highest):")
        sorted_by_attractions = sorted(valid_results, 
                                    key=lambda r: r.get("calculated_objectives", {}).get("attractions", 0), 
                                    reverse=True)
        for i, r in enumerate(sorted_by_attractions[:3]):
            calc_obj = r.get("calculated_objectives", {})
            print(f"  #{i+1}: Solution {r['solution_index']} - {calc_obj.get('attractions', 0)} "
                f"attractions, Quality: {calc_obj.get('quality', 0):.1f}, "
                f"Time: {calc_obj.get('time', 0):.1f} min, "
                f"Cost: CA$ {calc_obj.get('cost', 0):.2f}")
        
        # Top 3 por qualidade
        print("\nTop 3 by Quality (highest):")
        sorted_by_quality = sorted(valid_results, 
                                key=lambda r: r.get("calculated_objectives", {}).get("quality", 0), 
                                reverse=True)
        for i, r in enumerate(sorted_by_quality[:3]):
            calc_obj = r.get("calculated_objectives", {})
            print(f"  #{i+1}: Solution {r['solution_index']} - "
                f"Quality: {calc_obj.get('quality', 0):.1f}, "
                f"{calc_obj.get('attractions', 0)} attractions, "
                f"Time: {calc_obj.get('time', 0):.1f} min, "
                f"Cost: CA$ {calc_obj.get('cost', 0):.2f}")
        
        # Top 3 por menor tempo
        print("\nTop 3 by Time (lowest):")
        sorted_by_time = sorted(valid_results, 
                            key=lambda r: r.get("calculated_objectives", {}).get("time", 0))
        for i, r in enumerate(sorted_by_time[:3]):
            calc_obj = r.get("calculated_objectives", {})
            print(f"  #{i+1}: Solution {r['solution_index']} - "
                f"Time: {calc_obj.get('time', 0):.1f} min, "
                f"{calc_obj.get('attractions', 0)} attractions, "
                f"Quality: {calc_obj.get('quality', 0):.1f}, "
                f"Cost: CA$ {calc_obj.get('cost', 0):.2f}")
        
        # Top 3 por menor custo
        print("\nTop 3 by Cost (lowest):")
        sorted_by_cost = sorted(valid_results, 
                            key=lambda r: r.get("calculated_objectives", {}).get("cost", 0))
        for i, r in enumerate(sorted_by_cost[:3]):
            calc_obj = r.get("calculated_objectives", {})
            print(f"  #{i+1}: Solution {r['solution_index']} - "
                f"Cost: CA$ {calc_obj.get('cost', 0):.2f}, "
                f"{calc_obj.get('attractions', 0)} attractions, "
                f"Quality: {calc_obj.get('quality', 0):.1f}, "
                f"Time: {calc_obj.get('time', 0):.1f} min")
        
        # Heurística de melhor compromisso (normaliza e tira média)
        print("\nBest Compromise Solution:")
        
        normalized_results = []
        
        # Faixas por objetivo (para normalização 0..1)
        min_attractions = min(attractions) if attractions else 0
        max_attractions = max(attractions) if attractions else 1
        range_attractions = max_attractions - min_attractions
        
        min_quality = min(quality) if quality else 0
        max_quality = max(quality) if quality else 1
        range_quality = max_quality - min_quality
        
        min_time = min(time_values) if time_values else 0
        max_time = max(time_values) if time_values else 1
        range_time = max_time - min_time
        
        min_cost = min(cost) if cost else 0
        max_cost = max(cost) if cost else 1
        range_cost = max_cost - min_cost
        
        for r in valid_results:
            calc_obj = r.get("calculated_objectives", {})
            # Atrações e qualidade: maior é melhor -> normaliza direto
            norm_attractions = ((calc_obj.get("attractions", 0) - min_attractions) / range_attractions 
                             if range_attractions > 0 else 0)
            norm_quality = ((calc_obj.get("quality", 0) - min_quality) / range_quality 
                         if range_quality > 0 else 0)
            
            # Tempo e custo: menor é melhor -> 1 - normalização
            norm_time = 1 - ((calc_obj.get("time", 0) - min_time) / range_time 
                          if range_time > 0 else 0)
            norm_cost = 1 - ((calc_obj.get("cost", 0) - min_cost) / range_cost 
                          if range_cost > 0 else 0)
            
            avg_score = (norm_attractions + norm_quality + norm_time + norm_cost) / 4
            
            normalized_results.append({
                "solution_index": r["solution_index"],
                "score": avg_score,
                "objectives": calc_obj
            })
        
        if normalized_results:
            best_compromise = max(normalized_results, key=lambda r: r["score"])
            
            print(f"  Solution {best_compromise['solution_index']} - "
                f"Compromise Score: {best_compromise['score']:.4f}, "
                f"{best_compromise['objectives'].get('attractions', 0)} attractions, "
                f"Quality: {best_compromise['objectives'].get('quality', 0):.1f}, "
                f"Time: {best_compromise['objectives'].get('time', 0):.1f} min, "
                f"Cost: CA$ {best_compromise['objectives'].get('cost', 0):.2f}")
    
    def _format_time(self, time_in_minutes: float) -> str:
        # Formata minutos como HH:MM
        hours = int(time_in_minutes // 60)
        minutes = int(time_in_minutes % 60)
        return f"{hours:02d}:{minutes:02d}"


# Função CLI

def main():
    # Define argumentos de linha de comando
    parser = argparse.ArgumentParser(description="Verify NSGA-II solutions for Montreal Tourist Route Planning")
    parser.add_argument("--solution", "-s", required=False, 
                        default="test1.csv",
                        help="Path to the solution CSV file")
    parser.add_argument("--output", "-o", required=False, 
                        default="results/verification-results.csv",
                        help="Path to the output verification CSV file")
    parser.add_argument("--attractions", "-a", required=False, 
                        default="places/attractions.csv",
                        help="Path to the attractions CSV file")
    parser.add_argument("--hotels", "--hotel-file", required=False, 
                        default="places/hotels.csv",
                        help="Path to the hotels CSV file")
    parser.add_argument("--matrices", "-m", required=False, 
                        default="results",
                        help="Path to the transport matrices directory")
    
    args = parser.parse_args()
    
    try:
        # Monta caminhos absolutos a partir do diretório atual
        project_dir = os.getcwd()
        solution_path = os.path.join(project_dir, args.solution)
        output_path = os.path.join(project_dir, args.output)
        attractions_path = os.path.join(project_dir, args.attractions)
        hotels_path = os.path.join(project_dir, args.hotels)
        matrices_path = os.path.join(project_dir, args.matrices)
        
        # Echo de parâmetros
        print("Montreal Tourist Route Verification Tool")
        print(f"Solution file: {solution_path}")
        print(f"Output file: {output_path}")
        print(f"Attractions file: {attractions_path}")
        print(f"Hotels file: {hotels_path}")
        print(f"Matrices path: {matrices_path}")
        
        # Valida existência de arquivos/pastas
        if not os.path.exists(solution_path):
            print(f"ERROR: Solution file not found: {solution_path}")
            return 1
        
        if not os.path.exists(attractions_path):
            print(f"ERROR: Attractions file not found: {attractions_path}")
            return 1
        
        if not os.path.exists(hotels_path):
            print(f"ERROR: Hotels file not found: {hotels_path}")
            return 1
        
        if not os.path.exists(matrices_path):
            print(f"ERROR: Matrices directory not found: {matrices_path}")
            return 1
        
        # Garante diretório de saída
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Executa verificação
        start_time = time.time()
        verifier = SolutionVerifier(attractions_path, hotels_path, matrices_path)
        
        success = verifier.verify_solution_file(solution_path, output_path)
        
        execution_time = time.time() - start_time
        print(f"\nVerification completed in {execution_time:.2f} seconds")
        
        # Código de retorno compatível com CI
        return 0 if success else 1
        
    except Exception as e:
        # Erros de execução não previstos
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


# Entry point convencional
if __name__ == "__main__":
    sys.exit(main())
