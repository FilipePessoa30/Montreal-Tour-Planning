# -*- coding: utf-8 -*-
"""
Versão comentada linha a linha de movns/logger.py.
Objetivo: explicar cada instrução para facilitar entendimento e manutenção.
A lógica foi preservada exatamente; apenas comentários foram adicionados.
"""

import os  # Funções de sistema de arquivos (paths, diretórios)
import time  # Medição de tempo/cronômetro
import csv  # Escrita de CSVs
from typing import List, Dict, Any, Optional  # Tipagem opcional
import numpy as np  # Usado apenas para possíveis extensões/conversões


class MOVNSLogger:
    """
    Registrador (logger) para o algoritmo MOVNS.
    Armazena métricas por iteração e detalhamento das rotas/exporta em CSV.
    """

    def __init__(self, output_dir: str = "results"):  # Construtor com diretório de saída padrão
        self.output_dir = output_dir  # Guarda diretório para arquivos gerados
        self.execution_log = []  # Lista de dicionários com métricas por iteração
        self.detailed_solutions = []  # Lista de dicionários detalhando cada passo das rotas
        self.start_time = time.time()  # Marca de tempo inicial para calcular elapsed

        os.makedirs(output_dir, exist_ok=True)  # Garante existência do diretório de saída

    def log_iteration(self, iteration: int, archive_size: int, hypervolume: float,
                      spread: float, epsilon: Optional[float], objectives_stats: Dict[str, Any],
                      k_value: int, idle_iterations: int) -> None:
        exec_time = time.time() - self.start_time  # Tempo desde o início

        log_entry = {  # Monta registro com campos relevantes
            'iteration': iteration,
            'time': exec_time,
            'archive_size': archive_size,
            'hypervolume': hypervolume,
            'spread': spread,
            'epsilon': epsilon if epsilon is not None else "NA",
            'min_attractions': objectives_stats['min_attractions'],
            'avg_attractions': objectives_stats['avg_attractions'],
            'max_attractions': objectives_stats['max_attractions'],
            'min_quality': objectives_stats['min_quality'],
            'avg_quality': objectives_stats['avg_quality'],
            'max_quality': objectives_stats['max_quality'],
            'min_time': objectives_stats['min_time'],
            'avg_time': objectives_stats['avg_time'],
            'max_time': objectives_stats['max_time'],
            'min_cost': objectives_stats['min_cost'],
            'avg_cost': objectives_stats['avg_cost'],
            'max_cost': objectives_stats['max_cost'],
            'k_value': k_value,
            'idle_count': idle_iterations
        }

        self.execution_log.append(log_entry)  # Armazena no histórico

    def log_solution(self, solution_id: int, solution) -> None:  # Gera registros detalhados por atração/visita
        objectives = solution.get_objectives()  # Lê objetivos atuais (F1..F4)

        if solution.day1_route:  # Se existe rota do dia 1 (sábado)
            day1_attractions = solution.day1_route.get_attractions()  # Lista de atrações do dia 1
            for i, attraction in enumerate(day1_attractions):  # Itera cada atração e sua ordem
                start_time, end_time = self._format_time_info(solution.day1_route, i)  # Converte horários
                if i < len(solution.day1_route.transport_modes):  # Obtém modo de transporte do segmento
                    transport_mode = solution.day1_route.transport_modes[i]
                else:
                    transport_mode = None  # Caso falte segmento correspondente

                self.detailed_solutions.append({  # Adiciona registro detalhado
                    'solution_id': solution_id,
                    'day': 'Saturday',  # Dia correspondente
                    'order': i + 1,  # Ordem da atração no dia
                    'poi': attraction.name,  # Nome da atração
                    'start_time': start_time,  # Início formatado HH:MM
                    'end_time': end_time,  # Fim formatado HH:MM
                    'transport': transport_mode.name if transport_mode else 'WALK',  # Modo (enum->nome)
                    'duration': attraction.visit_time,  # Tempo de visita
                    'cost': attraction.cost,  # Custo da atração
                    'rating': attraction.rating,  # Nota
                    'hotel': solution.hotel.name,  # Hotel base
                    'f1': objectives[0],  # Objetivo 1: Nº atrações
                    'f2': objectives[1],  # Objetivo 2: Qualidade
                    'f3': objectives[2],  # Objetivo 3: Tempo total
                    'f4': objectives[3]   # Objetivo 4: Custo total
                })

        if solution.day2_route:  # Se existe rota do dia 2 (domingo)
            day2_attractions = solution.day2_route.get_attractions()  # Lista de atrações
            for i, attraction in enumerate(day2_attractions):  # Percorre todas
                start_time, end_time = self._format_time_info(solution.day2_route, i)  # Horários formatados
                if i < len(solution.day2_route.transport_modes):  # Modo de transporte do segmento
                    transport_mode = solution.day2_route.transport_modes[i]
                else:
                    transport_mode = None

                self.detailed_solutions.append({  # Registro detalhado
                    'solution_id': solution_id,
                    'day': 'Sunday',
                    'order': i + 1,
                    'poi': attraction.name,
                    'start_time': start_time,
                    'end_time': end_time,
                    'transport': transport_mode.name if transport_mode else 'WALK',
                    'duration': attraction.visit_time,
                    'cost': attraction.cost,
                    'rating': attraction.rating,
                    'hotel': solution.hotel.name,
                    'f1': objectives[0],
                    'f2': objectives[1],
                    'f3': objectives[2],
                    'f4': objectives[3]
                })

    def _format_time_info(self, day_route, attraction_index: int) -> tuple:  # Converte info temporal para strings
        if not day_route.time_info or attraction_index >= len(day_route.time_info):  # Verificações de segurança
            return ("", "")

        time_info = day_route.time_info[attraction_index+1]  # time_info[0] normalmente representa hotel->primeiro

        start_time = self._minutes_to_hhmm(time_info.arrival_time)  # Converte minutos em HH:MM chegada
        end_time = self._minutes_to_hhmm(time_info.departure_time)  # Converte minutos em HH:MM saída

        return (start_time, end_time)  # Retorna tupla de horários formatados

    def _minutes_to_hhmm(self, minutes):  # Converte minutos inteiros para string HH:MM
        if minutes is None:  # Se não definido
            return ""  # Retorna vazio

        hours = int(minutes // 60)  # Parte inteira de horas
        mins = int(minutes % 60)  # Minutos restantes
        return f"{hours:02d}:{mins:02d}"  # Formata sempre com dois dígitos

    def save_execution_log(self) -> None:  # Exporta log de execução para CSV
        if not self.execution_log:  # Nada a salvar
            return

        file_path = os.path.join(self.output_dir, "movns_execution_log.csv")  # Caminho do CSV

        try:
            with open(file_path, 'w', newline='') as csvfile:  # Abre arquivo para escrita
                fieldnames = list(self.execution_log[0].keys())  # Cabeçalho a partir da primeira linha

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')  # Writer com ;

                writer.writeheader()  # Escreve cabeçalho
                writer.writerows(self.execution_log)  # Escreve todas as linhas

            print(f"Saved {len(self.execution_log)} rows to {file_path}")  # Mensagem sucesso
        except Exception as e:  # Em caso de erro
            print(f"Error saving execution log: {str(e)}")  # Loga erro

    def save_solution_routes(self, solutions: List[Any]) -> None:  # Exporta detalhamento das rotas de um conjunto de soluções
        if not solutions:  # Sem soluções
            return

        self.detailed_solutions = []  # Reseta lista de detalhes

        for i, solution in enumerate(solutions):  # Para cada solução
            self.log_solution(i + 1, solution)  # Gera seus registros internos

        file_path = os.path.join(self.output_dir, "route_solution.csv")  # Caminho do CSV

        try:
            with open(file_path, 'w', newline='') as csvfile:  # Abre arquivo
                fieldnames = list(self.detailed_solutions[0].keys())  # Cabeçalho por chaves do primeiro item

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')  # Writer CSV

                writer.writeheader()  # Cabeçalho
                writer.writerows(self.detailed_solutions)  # Dados

            print(f"Saved {len(self.detailed_solutions)} rows to {file_path}")  # Sucesso
        except Exception as e:  # Erro
            print(f"Error saving solution routes: {str(e)}")  # Loga erro

    def elapsed_time(self) -> float:  # Tempo decorrido desde o início do logger
        return time.time() - self.start_time  # Retorna diferença em segundos
