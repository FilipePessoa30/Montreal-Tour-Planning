#!/usr/bin/env python3
"""
MOVNSConstructor - Versão Comentada
==================================

Este arquivo contém a versão totalmente comentada do constructor.py para facilitar o entendimento
de cada operação realizada. O MOVNSConstructor é responsável por:

1. Carregar e validar os dados (atrações, hotéis, matrizes de transporte)
2. Construir matrizes de compatibilidade entre locais
3. Gerar população inicial de soluções para o algoritmo MOVNS
4. Implementar diferentes estratégias de geração (max atrações, max qualidade, min tempo, min custo)
"""

import os
import random
import time
from typing import List, Dict, Tuple, Set, Optional, Any
from models import Attraction, Hotel, DailyRoute, TransportMode, Solution
from utils import Parser, Transport, normalize_string
from functools import lru_cache
import copy

class MOVNSConstructor:
    """
    Construtor para o algoritmo MOVNS (Multi-Objective Variable Neighborhood Search).
    
    Esta classe é responsável por:
    - Carregar dados de atrações, hotéis e matrizes de transporte
    - Validar consistência dos dados
    - Construir matrizes de compatibilidade para otimizar a geração de rotas
    - Gerar população inicial de soluções diversificadas
    """
    
    def __init__(self, attractions_file: str, hotels_file: str, matrices_path: str):
        """
        Inicializa o construtor carregando todos os dados necessários.
        
        Args:
            attractions_file: Caminho para o arquivo CSV com dados das atrações
            hotels_file: Caminho para o arquivo CSV com dados dos hotéis  
            matrices_path: Caminho para o diretório contendo as matrizes de tempo de viagem
        """
        print("=== INICIANDO CARREGAMENTO DE DADOS ===")
        
        # 1. CARREGAMENTO DE DADOS BÁSICOS
        print("Carregando atrações...")
        self.attractions = Parser.load_attractions(attractions_file)
        print(f"✓ {len(self.attractions)} atrações carregadas")
        
        print("Carregando hotéis...")
        self.hotels = Parser.load_hotels(hotels_file)
        print(f"✓ {len(self.hotels)} hotéis carregados")
        
        # 2. CARREGAMENTO DAS MATRIZES DE TRANSPORTE
        print("Carregando matrizes de transporte...")
        success = Parser.load_transport_matrices(matrices_path)
        if not success:
            raise RuntimeError("Falha ao carregar matrizes de transporte")
        print("✓ Matrizes de transporte carregadas com sucesso")
        
        # 3. CRIAÇÃO DE ÍNDICES PARA ACESSO RÁPIDO
        # Dicionários para busca rápida por nome
        self.attraction_by_name = {attr.name: attr for attr in self.attractions}
        self.hotel_by_name = {hotel.name: hotel for hotel in self.hotels}
        
        # Lista de hotéis que passaram na validação (será preenchida após validação)
        self.working_hotels = []
        
        # 4. PRÉ-CÁLCULO DE DISPONIBILIDADE DAS ATRAÇÕES
        print("=== PRÉ-CALCULANDO DISPONIBILIDADE DAS ATRAÇÕES ===")
        
        # Listas separadas para atrações abertas em cada dia da semana
        self.saturday_open_attractions = []
        self.sunday_open_attractions = []
        
        # Classifica cada atração por disponibilidade no weekend
        for attr in self.attractions:
            if attr.is_open_on_day(True):  # Sábado
                self.saturday_open_attractions.append(attr)
            
            if attr.is_open_on_day(False):  # Domingo
                self.sunday_open_attractions.append(attr)
                
        print(f"✓ {len(self.saturday_open_attractions)} atrações abertas no sábado")
        print(f"✓ {len(self.sunday_open_attractions)} atrações abertas no domingo")
        
        # 5. INICIALIZAÇÃO DE CACHES
        # Cache para validação de modos de transporte (evita recálculos)
        self._mode_validation_cache = {}
        
        # Matrizes de compatibilidade (serão preenchidas no próximo passo)
        self._attraction_compatibility_matrix = {}  # Atração → Atração
        self._hotel_attraction_compatibility = {}   # Hotel → Atração
        self._attraction_hotel_compatibility = {}   # Atração → Hotel
        
        # 6. CONSTRUÇÃO DAS MATRIZES DE COMPATIBILIDADE
        print("=== CONSTRUINDO MATRIZES DE COMPATIBILIDADE ===")
        self._build_compatibility_matrices()
        
        # 7. VALIDAÇÃO FINAL DOS DADOS
        print("=== VALIDANDO CONSISTÊNCIA DOS DADOS ===")
        self.validate_data_consistency()
        print("=== INICIALIZAÇÃO CONCLUÍDA ===\\n")
    
    def _build_compatibility_matrices(self):
        """
        Constrói matrizes de compatibilidade entre todos os pares de locais.
        
        Estas matrizes pré-calculam todas as conexões viáveis considerando:
        - Horários de funcionamento das atrações
        - Tempos de viagem entre locais
        - Modos de transporte disponíveis
        - Restrições de tempo (início 8h, fim 20h)
        
        Isso otimiza drasticamente a geração de rotas, evitando cálculos repetitivos.
        """
        print("Construindo matriz: Hotel → Atração...")
        
        # MATRIZ 1: HOTEL → ATRAÇÃO
        # Para cada hotel, calcula quais atrações são alcançáveis e em que condições
        for hotel in self.hotels:
            self._hotel_attraction_compatibility[hotel.name] = {}
            
            # SÁBADO: Verifica compatibilidade hotel-atração para sábado
            for attr in self.saturday_open_attractions:
                valid_modes = []  # Modos de transporte válidos
                
                # Testa cada modo de transporte disponível
                for mode in [TransportMode.CAR, TransportMode.BUS_WALK, TransportMode.SUBWAY_WALK, TransportMode.WALK]:
                    # Calcula tempo de viagem do hotel para a atração
                    travel_time = Transport.get_travel_time(hotel.name, attr.name, mode)
                    
                    if travel_time >= 0:  # Se conexão existe
                        # Calcula horário de chegada (partida às 8h + tempo de viagem)
                        arrival_time = 8 * 60 + travel_time  # 8h em minutos
                        
                        # Verifica se chega antes do fechamento
                        if arrival_time < attr.saturday_closing_time:
                            # Ajusta chegada para o horário de abertura se necessário
                            if arrival_time < attr.saturday_opening_time:
                                arrival_time = attr.saturday_opening_time
                            
                            # Verifica se há tempo suficiente para visitar
                            if arrival_time + attr.visit_time <= attr.saturday_closing_time:
                                valid_modes.append(mode)
                
                # Se encontrou modos válidos, armazena na matriz
                if valid_modes:
                    self._hotel_attraction_compatibility[hotel.name][attr.name] = {
                        "saturday": valid_modes,
                        "modes": valid_modes
                    }
            
            # DOMINGO: Mesmo processo para domingo
            for attr in self.sunday_open_attractions:
                valid_modes = []
                
                for mode in [TransportMode.CAR, TransportMode.BUS_WALK, TransportMode.SUBWAY_WALK, TransportMode.WALK]:
                    travel_time = Transport.get_travel_time(hotel.name, attr.name, mode)
                    
                    if travel_time >= 0:
                        arrival_time = 8 * 60 + travel_time
                        
                        if arrival_time < attr.sunday_closing_time:
                            if arrival_time < attr.sunday_opening_time:
                                arrival_time = attr.sunday_opening_time
                            
                            if arrival_time + attr.visit_time <= attr.sunday_closing_time:
                                valid_modes.append(mode)
                
                if valid_modes:
                    # Se atração já existe na matriz (aberta sábado E domingo)
                    if attr.name not in self._hotel_attraction_compatibility[hotel.name]:
                        self._hotel_attraction_compatibility[hotel.name][attr.name] = {"modes": valid_modes}
                    
                    # Adiciona dados específicos do domingo
                    self._hotel_attraction_compatibility[hotel.name][attr.name]["sunday"] = valid_modes
        
        print("Construindo matriz: Atração → Hotel...")
        
        # MATRIZ 2: ATRAÇÃO → HOTEL
        # Para cada atração, calcula para quais hotéis é possível retornar
        self._attraction_hotel_compatibility = {}
        
        for attr in self.attractions:
            if attr.name not in self._attraction_hotel_compatibility:
                self._attraction_hotel_compatibility[attr.name] = {}
            
            for hotel in self.hotels:
                valid_return_modes = []
                
                # Calcula o horário mais tarde possível para sair da atração
                latest_departure_saturday = -1
                latest_departure_sunday = -1
                
                if attr.is_open_on_day(True):  # Sábado
                    # Menor entre horário de fechamento e limite do dia (20h)
                    latest_departure_saturday = min(attr.saturday_closing_time, 20 * 60)
                
                if attr.is_open_on_day(False):  # Domingo
                    latest_departure_sunday = min(attr.sunday_closing_time, 20 * 60)
                
                # Testa cada modo de transporte para retorno
                for mode in [TransportMode.CAR, TransportMode.BUS_WALK, TransportMode.SUBWAY_WALK, TransportMode.WALK]:
                    travel_time = Transport.get_travel_time(attr.name, hotel.name, mode)
                    
                    if travel_time >= 0:
                        # Verifica se é possível chegar ao hotel antes das 20h
                        saturday_ok = (latest_departure_saturday != -1 and 
                                     latest_departure_saturday + travel_time <= 20 * 60)
                        sunday_ok = (latest_departure_sunday != -1 and 
                                   latest_departure_sunday + travel_time <= 20 * 60)
                        
                        if saturday_ok or sunday_ok:
                            valid_return_modes.append(mode)
                
                # Armazena modos válidos se existirem
                if valid_return_modes:
                    self._attraction_hotel_compatibility[attr.name][hotel.name] = valid_return_modes
        
        print("Construindo matriz: Atração → Atração...")
        
        # MATRIZ 3: ATRAÇÃO → ATRAÇÃO
        # Para cada par de atrações, calcula se é possível visitar uma após a outra
        for from_attr in self.attractions:
            self._attraction_compatibility_matrix[from_attr.name] = {}
            
            for to_attr in self.attractions:
                if from_attr.name != to_attr.name:  # Não considera a mesma atração
                    
                    # COMPATIBILIDADE SÁBADO
                    sat_valid_modes = []
                    if from_attr.is_open_on_day(True) and to_attr.is_open_on_day(True):
                        for mode in [TransportMode.CAR, TransportMode.BUS_WALK, TransportMode.SUBWAY_WALK, TransportMode.WALK]:
                            travel_time = Transport.get_travel_time(from_attr.name, to_attr.name, mode)
                            
                            if travel_time >= 0:
                                # Horário mais cedo possível para sair da primeira atração
                                earliest_departure = from_attr.saturday_opening_time + from_attr.visit_time
                                
                                # Horário mais tarde possível para sair
                                latest_departure = from_attr.saturday_closing_time
                                
                                # Horário de chegada na segunda atração
                                earliest_arrival = earliest_departure + travel_time
                                
                                # Verifica se chega antes do fechamento da segunda atração
                                if earliest_arrival < to_attr.saturday_closing_time:
                                    # Ajusta para horário de abertura se necessário
                                    if earliest_arrival < to_attr.saturday_opening_time:
                                        earliest_arrival = to_attr.saturday_opening_time
                                    
                                    # Verifica se há tempo para visitar a segunda atração
                                    if earliest_arrival + to_attr.visit_time <= to_attr.saturday_closing_time:
                                        sat_valid_modes.append(mode)
                    
                    # COMPATIBILIDADE DOMINGO (mesmo processo)
                    sun_valid_modes = []
                    if from_attr.is_open_on_day(False) and to_attr.is_open_on_day(False):
                        for mode in [TransportMode.CAR, TransportMode.BUS_WALK, TransportMode.SUBWAY_WALK, TransportMode.WALK]:
                            travel_time = Transport.get_travel_time(from_attr.name, to_attr.name, mode)
                            
                            if travel_time >= 0:
                                earliest_departure = from_attr.sunday_opening_time + from_attr.visit_time
                                latest_departure = from_attr.sunday_closing_time
                                earliest_arrival = earliest_departure + travel_time
                                
                                if earliest_arrival < to_attr.sunday_closing_time:
                                    if earliest_arrival < to_attr.sunday_opening_time:
                                        earliest_arrival = to_attr.sunday_opening_time
                                    
                                    if earliest_arrival + to_attr.visit_time <= to_attr.sunday_closing_time:
                                        sun_valid_modes.append(mode)
                    
                    # Armazena se há pelo menos um dia com modos válidos
                    if sat_valid_modes or sun_valid_modes:
                        self._attraction_compatibility_matrix[from_attr.name][to_attr.name] = {
                            "saturday": sat_valid_modes,
                            "sunday": sun_valid_modes
                        }
        
        # ESTATÍSTICAS DAS MATRIZES CONSTRUÍDAS
        hotel_attr_connections = sum(len(hotel_data) for hotel_data in self._hotel_attraction_compatibility.values())
        attr_attr_connections = sum(len(attr_data) for attr_data in self._attraction_compatibility_matrix.values())
        attr_hotel_connections = sum(len(attr_data) for attr_data in self._attraction_hotel_compatibility.values() if isinstance(attr_data, dict))
        
        print(f"✓ Matrizes de compatibilidade construídas:")
        print(f"  - {hotel_attr_connections} conexões hotel→atração")
        print(f"  - {attr_attr_connections} conexões atração→atração")
        print(f"  - {attr_hotel_connections} conexões atração→hotel")
    
    def validate_data_consistency(self) -> bool:
        """
        Valida a consistência dos dados carregados.
        
        Verifica se atrações e hotéis têm conexões válidas nas matrizes de transporte.
        Remove automaticamente entidades sem conexões válidas.
        
        Returns:
            bool: True se validação passou, False se dados insuficientes
        """
        print("Validando consistência dos dados...")
        
        # VALIDAÇÃO DAS ATRAÇÕES
        print(f"Validando {len(self.attractions)} atrações...")
        attraction_problems = 0
        valid_attractions = []
        
        for attraction in self.attractions:
            valid_connection_count = 0
            
            # Testa conexões com uma amostra de hotéis (otimização)
            sample_hotels = random.sample(self.hotels, min(10, len(self.hotels)))
            
            for hotel in sample_hotels:
                # Testa se há pelo menos um modo de transporte válido em ambas direções
                for mode in [TransportMode.CAR, TransportMode.BUS_WALK, TransportMode.SUBWAY_WALK, TransportMode.WALK]:
                    time_to = Transport.get_travel_time(hotel.name, attraction.name, mode)
                    time_from = Transport.get_travel_time(attraction.name, hotel.name, mode)
                    
                    if time_to >= 0 and time_from >= 0:
                        valid_connection_count += 1
                        break  # Encontrou pelo menos uma conexão válida
            
            # Considera atração válida se tem pelo menos 1 conexão
            if valid_connection_count >= 1:
                valid_attractions.append(attraction)
            else:
                print(f"ERRO: Atração '{attraction.name}' não tem conexões válidas")
                attraction_problems += 1
        
        print(f"✓ {len(valid_attractions)}/{len(self.attractions)} atrações válidas encontradas")
        
        # VALIDAÇÃO DOS HOTÉIS
        print(f"Validando {len(self.hotels)} hotéis...")
        hotel_problems = 0
        self.working_hotels = []  # Lista final de hotéis utilizáveis
        
        # Usa atrações válidas ou todas se nenhuma for válida
        sample_attractions = valid_attractions if valid_attractions else self.attractions
        sample_attractions = random.sample(sample_attractions, min(15, len(sample_attractions)))
        
        for hotel in self.hotels:
            valid_connection_count = 0
            
            # Testa conexões com uma amostra de atrações
            for attr in sample_attractions:
                for mode in [TransportMode.CAR, TransportMode.BUS_WALK, TransportMode.SUBWAY_WALK, TransportMode.WALK]:
                    time_to = Transport.get_travel_time(hotel.name, attr.name, mode)
                    time_from = Transport.get_travel_time(attr.name, hotel.name, mode)
                    
                    if time_to >= 0 and time_from >= 0:
                        valid_connection_count += 1
                        break
            
            # Considera hotel válido se tem pelo menos 1 conexão
            if valid_connection_count >= 1:
                self.working_hotels.append(hotel)
            else:
                print(f"ERRO: Hotel '{hotel.name}' não tem conexões válidas")
                hotel_problems += 1
        
        # Ordena hotéis por rating (melhores primeiro) para otimizar geração
        self.working_hotels.sort(key=lambda h: h.rating, reverse=True)
        
        print(f"✓ {len(self.working_hotels)}/{len(self.hotels)} hotéis funcionais encontrados")
        
        # VERIFICA SE HÁ DADOS SUFICIENTES PARA CONTINUAR
        if (attraction_problems > 0 or hotel_problems > 0) and valid_attractions and self.working_hotels:
            print(f"Encontrados {attraction_problems} problemas de atração e {hotel_problems} problemas de hotel.")
            print(f"Continuando com {len(valid_attractions)} atrações válidas e {len(self.working_hotels)} hotéis funcionais.")
            return True
        
        if not valid_attractions or not self.working_hotels:
            raise RuntimeError(f"ERRO: Não é possível continuar - encontradas apenas {len(valid_attractions)} atrações válidas e {len(self.working_hotels)} hotéis funcionais.")
        
        return True
    
    def generate_initial_population(self, population_size=100) -> List[Solution]:
        """
        Gera a população inicial de soluções para o algoritmo MOVNS.
        
        Implementa uma estratégia diversificada:
        - 20% soluções focadas em maximizar número de atrações
        - 20% soluções focadas em maximizar qualidade (ratings)
        - 20% soluções focadas em minimizar tempo de viagem
        - 20% soluções focadas em minimizar custo
        - 20% soluções totalmente aleatórias
        
        Args:
            population_size: Número de soluções a gerar
            
        Returns:
            List[Solution]: Lista de soluções válidas geradas
        """
        solutions = []
        start_time = time.time()
        
        # Contadores para controle do processo
        attempt_count = 0
        max_attempts = population_size * 10  # Máximo 10x tentativas
        
        print(f"=== INICIANDO GERAÇÃO DE POPULAÇÃO ===")
        print(f"Objetivo: {population_size} soluções")
        print(f"Hotéis disponíveis: {len(self.working_hotels)}")
        
        # ESTRATÉGIA 1: MAXIMIZAR NÚMERO DE ATRAÇÕES (20%)
        print("\\n1. Gerando soluções focadas em MÁXIMO DE ATRAÇÕES...")
        target_count = population_size // 5
        for i in range(target_count):
            solution = self._generate_max_attractions_solution()
            if solution:
                solutions.append(solution)
                print(f"   ✓ Solução {len(solutions)}: {solution.get_objectives()[0]} atrações")
        
        # ESTRATÉGIA 2: MAXIMIZAR QUALIDADE (20%)
        print("\\n2. Gerando soluções focadas em MÁXIMA QUALIDADE...")
        for i in range(target_count):
            solution = self._generate_max_quality_solution()
            if solution:
                solutions.append(solution)
                print(f"   ✓ Solução {len(solutions)}: qualidade {solution.get_objectives()[1]:.1f}")
        
        # ESTRATÉGIA 3: MINIMIZAR TEMPO DE VIAGEM (20%)
        print("\\n3. Gerando soluções focadas em MÍNIMO TEMPO...")
        for i in range(target_count):
            solution = self._generate_min_time_solution()
            if solution:
                solutions.append(solution)
                print(f"   ✓ Solução {len(solutions)}: {solution.get_objectives()[2]:.1f} min")
        
        # ESTRATÉGIA 4: MINIMIZAR CUSTO (20%)
        print("\\n4. Gerando soluções focadas em MÍNIMO CUSTO...")
        for i in range(target_count):
            solution = self._generate_min_cost_solution()
            if solution:
                solutions.append(solution)
                print(f"   ✓ Solução {len(solutions)}: CA$ {solution.get_objectives()[3]:.2f}")
        
        # ESTRATÉGIA 5: SOLUÇÕES ALEATÓRIAS (restante)
        print("\\n5. Gerando soluções ALEATÓRIAS...")
        
        while len(solutions) < population_size and attempt_count < max_attempts:
            attempt_count += 1
            
            try:
                # Escolhe hotel aleatório entre os funcionais
                hotel = random.choice(self.working_hotels)
                
                # Conjunto para evitar visitar mesma atração nos dois dias
                assigned_attractions = set()
                
                # Cria rotas para sábado e domingo
                day1_route = DailyRoute(is_saturday=True)
                day2_route = DailyRoute(is_saturday=False)
                
                # Define hotel para ambas as rotas
                day1_route.set_hotel(hotel)
                day2_route.set_hotel(hotel)
                
                # Gera rota do sábado
                day1_success = self._generate_day_route_incremental(
                    day1_route, 
                    assigned_attractions
                )
                
                if day1_success:
                    # Marca atrações do sábado como usadas
                    for attr in day1_route.get_attractions():
                        assigned_attractions.add(attr.name)
                    
                    # Gera rota do domingo
                    day2_success = self._generate_day_route_incremental(
                        day2_route, 
                        assigned_attractions
                    )
                    
                    if day2_success:
                        # Cria solução completa
                        solution = Solution(hotel, day1_route, day2_route)
                        
                        total_attractions = day1_route.get_num_attractions() + day2_route.get_num_attractions()
                        if total_attractions > 0:
                            # Calcula objetivos e adiciona à população
                            solution.objectives = solution.calculate_objectives()
                            solutions.append(solution)
                            
                            # Relatório de progresso a cada 10 soluções
                            if len(solutions) % 10 == 0:
                                print(f"   ✓ Solução {len(solutions)}/{population_size}: {total_attractions} atrações")
                                
            except Exception as e:
                print(f"   ✗ Erro gerando solução: {str(e)}")
            
            # Relatório de progresso a cada 100 tentativas
            if attempt_count % 100 == 0:
                elapsed = time.time() - start_time
                print(f"   Tentativas: {attempt_count}, Soluções: {len(solutions)}/{population_size}, Tempo: {elapsed:.2f}s")
        
        # RELATÓRIO FINAL
        elapsed = time.time() - start_time
        print(f"\\n=== GERAÇÃO CONCLUÍDA ===")
        print(f"✓ {len(solutions)} soluções válidas geradas em {elapsed:.2f} segundos")
        print(f"✓ Taxa de sucesso: {len(solutions)/attempt_count*100:.1f}% ({len(solutions)}/{attempt_count} tentativas)")
        
        return solutions
    
    def _generate_max_attractions_solution(self) -> Optional[Solution]:
        """
        Gera uma solução focada em maximizar o número de atrações visitadas.
        
        Estratégia:
        - Usa hotéis com melhor rating (top 10)
        - Prioriza atrações com menor tempo de visita
        - Tenta encaixar o máximo de atrações possível
        
        Returns:
            Optional[Solution]: Solução gerada ou None se falhou
        """
        # Tenta com vários hotéis bem avaliados
        for _ in range(min(10, len(self.working_hotels))):
            hotel = random.choice(self.working_hotels[:10])  # Top 10 hotéis
            
            assigned_attractions = set()
            
            day1_route = DailyRoute(is_saturday=True)
            day2_route = DailyRoute(is_saturday=False)
            
            day1_route.set_hotel(hotel)
            day2_route.set_hotel(hotel)
            
            # Gera rota do sábado focada em máximo de atrações
            day1_success = self._generate_day_route_max_attractions(
                day1_route, 
                assigned_attractions
            )
            
            if day1_success:
                # Marca atrações usadas
                for attr in day1_route.get_attractions():
                    assigned_attractions.add(attr.name)
                
                # Gera rota do domingo
                day2_success = self._generate_day_route_max_attractions(
                    day2_route, 
                    assigned_attractions
                )
                
                if day2_success:
                    solution = Solution(hotel, day1_route, day2_route)
                    solution.objectives = solution.calculate_objectives()
                    return solution
        
        return None
    
    def _generate_max_quality_solution(self) -> Optional[Solution]:
        """
        Gera uma solução focada em maximizar a qualidade (ratings).
        
        Estratégia:
        - Usa hotéis com melhor rating (top 5)
        - Prioriza atrações com melhor rating
        - Foca na qualidade em vez da quantidade
        
        Returns:
            Optional[Solution]: Solução gerada ou None se falhou
        """
        # Escolhe entre os 5 melhores hotéis
        top_hotels = sorted(self.working_hotels, key=lambda h: h.rating, reverse=True)[:5]
        hotel = random.choice(top_hotels)
        
        assigned_attractions = set()
        
        day1_route = DailyRoute(is_saturday=True)
        day2_route = DailyRoute(is_saturday=False)
        
        day1_route.set_hotel(hotel)
        day2_route.set_hotel(hotel)
        
        # Gera rotas focadas em qualidade
        day1_success = self._generate_day_route_max_quality(
            day1_route, 
            assigned_attractions
        )
        
        if day1_success:
            for attr in day1_route.get_attractions():
                assigned_attractions.add(attr.name)
            
            day2_success = self._generate_day_route_max_quality(
                day2_route, 
                assigned_attractions
            )
            
            if day2_success:
                solution = Solution(hotel, day1_route, day2_route)
                solution.objectives = solution.calculate_objectives()
                return solution
        
        # Se falhou, gera solução aleatória como fallback
        return self._generate_random_solution()
    
    def _generate_min_time_solution(self) -> Optional[Solution]:
        """
        Gera uma solução focada em minimizar tempo de viagem.
        
        Estratégia:
        - Prioriza atrações próximas ao hotel
        - Usa transporte a pé quando possível
        - Constrói rotas compactas geograficamente
        
        Returns:
            Optional[Solution]: Solução gerada ou None se falhou
        """
        # Tenta com vários hotéis
        for _ in range(min(10, len(self.working_hotels))):
            hotel = random.choice(self.working_hotels)
            
            assigned_attractions = set()
            
            day1_route = DailyRoute(is_saturday=True)
            day2_route = DailyRoute(is_saturday=False)
            
            day1_route.set_hotel(hotel)
            day2_route.set_hotel(hotel)
            
            # Gera rotas focadas em tempo mínimo
            day1_success = self._generate_day_route_min_time(
                day1_route, 
                assigned_attractions
            )
            
            if day1_success:
                for attr in day1_route.get_attractions():
                    assigned_attractions.add(attr.name)
                
                day2_success = self._generate_day_route_min_time(
                    day2_route, 
                    assigned_attractions
                )
                
                if day2_success:
                    solution = Solution(hotel, day1_route, day2_route)
                    solution.objectives = solution.calculate_objectives()
                    return solution
        
        return None
    
    def _generate_min_cost_solution(self) -> Optional[Solution]:
        """
        Gera uma solução focada em minimizar custo total.
        
        Estratégia:
        - Usa hotéis mais baratos (top 5)
        - Prioriza atrações gratuitas
        - Evita transporte carro (mais caro)
        
        Returns:
            Optional[Solution]: Solução gerada ou None se falhou
        """
        # Escolhe entre os 5 hotéis mais baratos
        cheap_hotels = sorted(self.working_hotels, key=lambda h: h.price)[:5]
        hotel = random.choice(cheap_hotels)
        
        assigned_attractions = set()
        
        day1_route = DailyRoute(is_saturday=True)
        day2_route = DailyRoute(is_saturday=False)
        
        day1_route.set_hotel(hotel)
        day2_route.set_hotel(hotel)
        
        # Gera rotas focadas em custo mínimo
        day1_success = self._generate_day_route_min_cost(
            day1_route, 
            assigned_attractions
        )
        
        if day1_success:
            for attr in day1_route.get_attractions():
                assigned_attractions.add(attr.name)
            
            day2_success = self._generate_day_route_min_cost(
                day2_route, 
                assigned_attractions
            )
            
            if day2_success:
                solution = Solution(hotel, day1_route, day2_route)
                solution.objectives = solution.calculate_objectives()
                return solution
        
        # Se falhou, gera solução aleatória como fallback
        return self._generate_random_solution()
    
    def _generate_random_solution(self) -> Optional[Solution]:
        """
        Gera uma solução completamente aleatória.
        
        Usado como fallback quando estratégias específicas falham.
        
        Returns:
            Optional[Solution]: Solução gerada ou None se falhou
        """
        hotel = random.choice(self.working_hotels)
        
        assigned_attractions = set()
        
        day1_route = DailyRoute(is_saturday=True)
        day2_route = DailyRoute(is_saturday=False)
        
        day1_route.set_hotel(hotel)
        day2_route.set_hotel(hotel)
        
        # Gera rotas incrementais aleatórias
        day1_success = self._generate_day_route_incremental(
            day1_route, 
            assigned_attractions
        )
        
        if day1_success:
            for attr in day1_route.get_attractions():
                assigned_attractions.add(attr.name)
            
            day2_success = self._generate_day_route_incremental(
                day2_route, 
                assigned_attractions
            )
            
            if day2_success:
                solution = Solution(hotel, day1_route, day2_route)
                solution.objectives = solution.calculate_objectives()
                return solution
        
        return None
    
    def _generate_day_route_incremental(self, day_route: DailyRoute, 
                                       assigned_attractions: Set[str]) -> bool:
        """
        Gera uma rota diária adicionando atrações incrementalmente.
        
        Estratégia padrão: adiciona atrações uma por vez até não conseguir mais.
        
        Args:
            day_route: Rota do dia a ser preenchida
            assigned_attractions: Atrações já usadas (para evitar duplicatas)
            
        Returns:
            bool: True se gerou rota válida, False caso contrário
        """
        hotel = day_route.hotel
        is_saturday = day_route.is_saturday
        day_key = "saturday" if is_saturday else "sunday"
        
        # Copia conjunto para não modificar o original durante a geração
        used_attraction_names = set(assigned_attractions)
        
        max_attractions = 5  # Limite máximo por dia
        
        # LOOP PRINCIPAL: Adiciona atrações incrementalmente
        while day_route.get_num_attractions() < max_attractions:
            # Determina ponto de partida atual
            if day_route.get_num_attractions() == 0:
                from_name = hotel.name  # Primeira atração: parte do hotel
                is_from_hotel = True
            else:
                from_name = day_route.get_attractions()[-1].name  # Próximas: da última atração
                is_from_hotel = False
            
            # Encontra candidatos à próxima atração
            candidates = self._find_next_attraction_candidates(
                from_name, 
                is_from_hotel, 
                hotel.name, 
                is_saturday, 
                used_attraction_names
            )
            
            # Se não há candidatos, para o loop
            if not candidates:
                break
            
            # Escolhe candidato aleatório
            selected = random.choice(candidates)
            
            # Tenta adicionar a atração à rota
            if not day_route.add_attraction(selected["attraction"], selected["to_mode"]):
                # Se falhou, marca como usada para não tentar novamente
                used_attraction_names.add(selected["attraction"].name)
                continue
            
            # Sucesso: marca atração como usada
            used_attraction_names.add(selected["attraction"].name)
        
        # CONFIGURAÇÃO DO RETORNO AO HOTEL
        if day_route.get_num_attractions() > 0:
            last_attraction = day_route.get_attractions()[-1]
            
            # Busca modos válidos para retornar ao hotel
            valid_return_modes = day_route.get_valid_return_modes()
            
            # Se não encontrou, consulta matriz de compatibilidade
            if not valid_return_modes:
                if (last_attraction.name in self._attraction_hotel_compatibility and 
                    hotel.name in self._attraction_hotel_compatibility[last_attraction.name]):
                    valid_return_modes = self._attraction_hotel_compatibility[last_attraction.name][hotel.name]
            
            # Se ainda não tem modos válidos, falha
            if not valid_return_modes:
                return False
            
            # Escolhe modo de retorno aleatório
            return_mode = random.choice(valid_return_modes)
            if not day_route.set_return_mode(return_mode):
                return False
        
        # Verifica se rota é válida e tem pelo menos uma atração
        return day_route.get_num_attractions() > 0 and day_route.is_valid()
    
    def _generate_day_route_max_attractions(self, day_route: DailyRoute, 
                                          assigned_attractions: Set[str]) -> bool:
        """
        Gera rota diária focada em maximizar número de atrações.
        
        Estratégia:
        - Ordena atrações por tempo de visita (mais rápidas primeiro)
        - Tenta encaixar o máximo possível
        - Para quando atinge 5 atrações ou não consegue mais
        
        Args:
            day_route: Rota do dia a ser preenchida
            assigned_attractions: Atrações já usadas
            
        Returns:
            bool: True se gerou rota válida, False caso contrário
        """
        hotel = day_route.hotel
        is_saturday = day_route.is_saturday
        day_key = "saturday" if is_saturday else "sunday"
        
        used_attraction_names = set(assigned_attractions)
        
        # Filtra atrações disponíveis no dia
        available_attractions = (self.saturday_open_attractions if is_saturday 
                               else self.sunday_open_attractions)
        
        available_attractions = [attr for attr in available_attractions 
                               if attr.name not in used_attraction_names]
        
        # ORDENA POR TEMPO DE VISITA (menores primeiro para encaixar mais)
        available_attractions.sort(key=lambda a: a.visit_time)
        
        # TENTA ADICIONAR CADA ATRAÇÃO EM ORDEM
        for attr in available_attractions:
            if attr.name in used_attraction_names:
                continue
            
            # Determina ponto de partida
            if day_route.get_num_attractions() == 0:
                from_name = hotel.name
            else:
                from_name = day_route.get_attractions()[-1].name
            
            # Verifica se há transporte válido
            valid_modes = self._get_valid_transport_modes(from_name, attr.name)
            if not valid_modes:
                continue
            
            # Verifica se há caminho de volta ao hotel
            if (attr.name in self._attraction_hotel_compatibility and 
                hotel.name in self._attraction_hotel_compatibility[attr.name]):
                
                # Escolhe modo preferido (otimizado)
                to_mode = self._choose_preferred_mode(valid_modes)
                
                # Tenta adicionar
                if day_route.add_attraction(attr, to_mode):
                    used_attraction_names.add(attr.name)
                    
                    # Para se atingiu limite máximo
                    if day_route.get_num_attractions() >= 5:
                        break
        
        # Configura retorno ao hotel
        if day_route.get_num_attractions() > 0:
            last_attraction = day_route.get_attractions()[-1]
            valid_return_modes = self._get_valid_transport_modes(last_attraction.name, hotel.name)
            
            if valid_return_modes:
                return_mode = self._choose_preferred_mode(valid_return_modes)
                day_route.set_return_mode(return_mode)
        
        return day_route.get_num_attractions() > 0 and day_route.is_valid()
    
    def _generate_day_route_max_quality(self, day_route: DailyRoute, 
                                       assigned_attractions: Set[str]) -> bool:
        """
        Gera rota diária focada em maximizar qualidade (ratings).
        
        Estratégia:
        - Ordena atrações por rating (melhores primeiro)
        - Prioriza top 10 atrações
        - Preenche resto aleatoriamente se sobrar tempo
        
        Args:
            day_route: Rota do dia a ser preenchida
            assigned_attractions: Atrações já usadas
            
        Returns:
            bool: True se gerou rota válida, False caso contrário
        """
        hotel = day_route.hotel
        is_saturday = day_route.is_saturday
        
        used_attraction_names = set(assigned_attractions)
        
        # Filtra atrações disponíveis
        available_attractions = (self.saturday_open_attractions if is_saturday 
                               else self.sunday_open_attractions)
        
        available_attractions = [attr for attr in available_attractions 
                               if attr.name not in used_attraction_names]
        
        # ORDENA POR RATING (melhores primeiro)
        available_attractions.sort(key=lambda a: a.rating, reverse=True)
        
        # FASE 1: PRIORIZA TOP 10 ATRAÇÕES POR QUALIDADE
        for attr in available_attractions[:10]:
            if attr.name in used_attraction_names:
                continue
            
            if day_route.get_num_attractions() == 0:
                from_name = hotel.name
            else:
                from_name = day_route.get_attractions()[-1].name
            
            valid_modes = self._get_valid_transport_modes(from_name, attr.name)
            if not valid_modes:
                continue
            
            # Verifica retorno ao hotel
            if (attr.name in self._attraction_hotel_compatibility and 
                hotel.name in self._attraction_hotel_compatibility[attr.name]):
                
                to_mode = self._choose_preferred_mode(valid_modes)
                
                if day_route.add_attraction(attr, to_mode):
                    used_attraction_names.add(attr.name)
                    
                    # Para após 3 atrações de alta qualidade
                    if day_route.get_num_attractions() >= 3:
                        break
        
        # FASE 2: PREENCHE RESTANTE ALEATORIAMENTE (se ainda há espaço)
        if day_route.get_num_attractions() < 5:
            remaining = list(available_attractions)
            random.shuffle(remaining)  # Embaralha para variedade
            
            for attr in remaining:
                if attr.name in used_attraction_names:
                    continue
                
                if day_route.get_num_attractions() == 0:
                    from_name = hotel.name
                else:
                    from_name = day_route.get_attractions()[-1].name
                
                valid_modes = self._get_valid_transport_modes(from_name, attr.name)
                if not valid_modes:
                    continue
                
                to_mode = self._choose_preferred_mode(valid_modes)
                
                if day_route.add_attraction(attr, to_mode):
                    used_attraction_names.add(attr.name)
                    
                    if day_route.get_num_attractions() >= 5:
                        break
        
        # Configura retorno
        if day_route.get_num_attractions() > 0:
            last_attraction = day_route.get_attractions()[-1]
            valid_return_modes = self._get_valid_transport_modes(last_attraction.name, hotel.name)
            
            if valid_return_modes:
                return_mode = self._choose_preferred_mode(valid_return_modes)
                day_route.set_return_mode(return_mode)
        
        return day_route.get_num_attractions() > 0 and day_route.is_valid()
    
    def _generate_day_route_min_time(self, day_route: DailyRoute, 
                                    assigned_attractions: Set[str]) -> bool:
        """
        Gera rota diária focada em minimizar tempo de viagem.
        
        Estratégia:
        - Prioriza atrações próximas ao hotel (< 30 min a pé)
        - Constrói rotas geograficamente compactas
        - Usa transporte a pé sempre que possível
        
        Args:
            day_route: Rota do dia a ser preenchida
            assigned_attractions: Atrações já usadas
            
        Returns:
            bool: True se gerou rota válida, False caso contrário
        """
        hotel = day_route.hotel
        is_saturday = day_route.is_saturday
        
        used_attraction_names = set(assigned_attractions)
        
        available_attractions = (self.saturday_open_attractions if is_saturday 
                               else self.sunday_open_attractions)
        
        available_attractions = [attr for attr in available_attractions 
                               if attr.name not in used_attraction_names]
        
        # FASE 1: BUSCA ATRAÇÕES PRÓXIMAS AO HOTEL (< 30 min a pé)
        hotel_close_attractions = []
        for attr in available_attractions:
            travel_time = Transport.get_travel_time(hotel.name, attr.name, TransportMode.WALK)
            if travel_time >= 0 and travel_time < 30:  # Menos de 30 minutos a pé
                hotel_close_attractions.append((attr, travel_time))
        
        # Ordena por tempo de caminhada
        hotel_close_attractions.sort(key=lambda x: x[1])
        
        # Se há atrações próximas, escolhe uma das 3 mais próximas
        if hotel_close_attractions:
            attr, _ = random.choice(hotel_close_attractions[:3])
            
            if day_route.add_attraction(attr, TransportMode.WALK):
                used_attraction_names.add(attr.name)
        
        # FASE 2: SE NÃO CONSEGUIU COMEÇAR COM CAMINHADA, USA QUALQUER MODO
        if day_route.get_num_attractions() == 0:
            for attr in available_attractions:
                valid_modes = self._get_valid_transport_modes(hotel.name, attr.name)
                if not valid_modes:
                    continue
                
                # Escolhe modo mais rápido
                to_mode = min(valid_modes, key=lambda m: Transport.get_travel_time(hotel.name, attr.name, m))
                
                if day_route.add_attraction(attr, to_mode):
                    used_attraction_names.add(attr.name)
                    break
        
        # FASE 3: ADICIONA ATRAÇÕES PRÓXIMAS À ÚLTIMA VISITADA
        while day_route.get_num_attractions() < 3:
            if day_route.get_num_attractions() == 0:
                break
            
            last_attr = day_route.get_attractions()[-1]
            
            # Busca atrações próximas à última visitada
            close_attractions = []
            for attr in available_attractions:
                if attr.name in used_attraction_names:
                    continue
                
                travel_time = Transport.get_travel_time(last_attr.name, attr.name, TransportMode.WALK)
                if travel_time >= 0:
                    close_attractions.append((attr, travel_time))
            
            # Ordena por proximidade
            close_attractions.sort(key=lambda x: x[1])
            
            # Tenta adicionar uma das 5 mais próximas
            added = False
            for attr, _ in close_attractions[:5]:
                if day_route.add_attraction(attr, TransportMode.WALK):
                    used_attraction_names.add(attr.name)
                    added = True
                    break
            
            # Se não conseguiu adicionar nenhuma, para
            if not added:
                break
        
        # Configura retorno com modo mais rápido
        if day_route.get_num_attractions() > 0:
            last_attraction = day_route.get_attractions()[-1]
            valid_return_modes = self._get_valid_transport_modes(last_attraction.name, hotel.name)
            
            if valid_return_modes:
                # Escolhe modo mais rápido para retorno
                return_mode = min(valid_return_modes, 
                                key=lambda m: Transport.get_travel_time(last_attraction.name, hotel.name, m))
                day_route.set_return_mode(return_mode)
        
        return day_route.get_num_attractions() > 0 and day_route.is_valid()
    
    def _generate_day_route_min_cost(self, day_route: DailyRoute, 
                                   assigned_attractions: Set[str]) -> bool:
        """
        Gera rota diária focada em minimizar custo total.
        
        Estratégia:
        - Prioriza atrações gratuitas (custo = 0)
        - Evita transporte de carro (mais caro)
        - Considera apenas atrações baratas (< CA$15)
        
        Args:
            day_route: Rota do dia a ser preenchida
            assigned_attractions: Atrações já usadas
            
        Returns:
            bool: True se gerou rota válida, False caso contrário
        """
        hotel = day_route.hotel
        is_saturday = day_route.is_saturday
        
        used_attraction_names = set(assigned_attractions)
        
        available_attractions = (self.saturday_open_attractions if is_saturday 
                               else self.sunday_open_attractions)
        
        available_attractions = [attr for attr in available_attractions 
                               if attr.name not in used_attraction_names]
        
        # Ordena por custo (mais baratas primeiro)
        available_attractions.sort(key=lambda a: a.cost)
        
        # FASE 1: PRIORIZA ATRAÇÕES GRATUITAS
        free_attractions = [attr for attr in available_attractions if attr.cost == 0]
        
        for attr in free_attractions:
            if day_route.get_num_attractions() == 0:
                from_name = hotel.name
            else:
                from_name = day_route.get_attractions()[-1].name
            
            valid_modes = self._get_valid_transport_modes(from_name, attr.name)
            # Prefere modos baratos (evita carro)
            cheap_modes = [m for m in valid_modes if m != TransportMode.CAR]
            
            if not cheap_modes and not valid_modes:
                continue
            
            to_mode = self._choose_preferred_mode(cheap_modes if cheap_modes else valid_modes)
            
            if day_route.add_attraction(attr, to_mode):
                used_attraction_names.add(attr.name)
                
                # Para após 4 atrações gratuitas
                if day_route.get_num_attractions() >= 4:
                    break
        
        # FASE 2: ADICIONA ATRAÇÕES BARATAS (< CA$15) SE AINDA HÁ ESPAÇO
        if day_route.get_num_attractions() < 2:
            for attr in available_attractions:
                if attr.name in used_attraction_names or attr.cost > 15:
                    continue
                
                if day_route.get_num_attractions() == 0:
                    from_name = hotel.name
                else:
                    from_name = day_route.get_attractions()[-1].name
                
                valid_modes = self._get_valid_transport_modes(from_name, attr.name)
                cheap_modes = [m for m in valid_modes if m != TransportMode.CAR]
                
                if not cheap_modes and not valid_modes:
                    continue
                
                to_mode = self._choose_preferred_mode(cheap_modes if cheap_modes else valid_modes)
                
                if day_route.add_attraction(attr, to_mode):
                    used_attraction_names.add(attr.name)
                    
                    if day_route.get_num_attractions() >= 3:
                        break
        
        # Configura retorno com modo barato
        if day_route.get_num_attractions() > 0:
            last_attraction = day_route.get_attractions()[-1]
            valid_return_modes = self._get_valid_transport_modes(last_attraction.name, hotel.name)
            
            # Prefere modos baratos para retorno
            cheap_return_modes = [m for m in valid_return_modes if m != TransportMode.CAR]
            
            if cheap_return_modes:
                return_mode = self._choose_preferred_mode(cheap_return_modes)
            elif valid_return_modes:
                return_mode = self._choose_preferred_mode(valid_return_modes)
            else:
                return False
            
            day_route.set_return_mode(return_mode)
        
        return day_route.get_num_attractions() > 0 and day_route.is_valid()
    
    def _find_next_attraction_candidates(self, from_name: str, is_from_hotel: bool, 
                                       hotel_name: str, is_saturday: bool, 
                                       used_attractions: Set[str]) -> List[Dict]:
        """
        Encontra candidatos para a próxima atração a ser visitada.
        
        Usa as matrizes de compatibilidade pré-calculadas para encontrar rapidamente
        todas as atrações que podem ser visitadas a partir do local atual.
        
        Args:
            from_name: Nome do local atual (hotel ou atração)
            is_from_hotel: True se partindo do hotel, False se de atração
            hotel_name: Nome do hotel (para verificar retorno)
            is_saturday: True para sábado, False para domingo
            used_attractions: Atrações já visitadas (para evitar)
            
        Returns:
            List[Dict]: Lista de candidatos com atração e modo de transporte
        """
        day_key = "saturday" if is_saturday else "sunday"
        candidates = []
        available_attractions = self.saturday_open_attractions if is_saturday else self.sunday_open_attractions
        
        # CASO 1: PARTINDO DO HOTEL
        if is_from_hotel:
            if hotel_name in self._hotel_attraction_compatibility:
                for attr_name, compat_data in self._hotel_attraction_compatibility[hotel_name].items():
                    # Pula se atração já foi usada ou não está disponível no dia
                    if attr_name in used_attractions or day_key not in compat_data:
                        continue
                    
                    # Busca objeto da atração
                    attr = next((a for a in available_attractions if a.name == attr_name), None)
                    if not attr:
                        continue
                    
                    # Modos válidos para chegar à atração
                    valid_to_modes = compat_data[day_key]
                    
                    # IMPORTANTE: Verifica se há caminho de volta ao hotel
                    has_return_path = False
                    if (attr_name in self._attraction_hotel_compatibility and 
                        hotel_name in self._attraction_hotel_compatibility[attr_name]):
                        has_return_path = len(self._attraction_hotel_compatibility[attr_name][hotel_name]) > 0
                    
                    # Só adiciona se há caminho de volta
                    if has_return_path:
                        for to_mode in valid_to_modes:
                            candidates.append({
                                "attraction": attr,
                                "to_mode": to_mode,
                            })
        
        # CASO 2: PARTINDO DE UMA ATRAÇÃO
        else:
            if from_name in self._attraction_compatibility_matrix:
                for next_attr_name, compat_data in self._attraction_compatibility_matrix[from_name].items():
                    # Pula se atração já foi usada ou não disponível no dia
                    if next_attr_name in used_attractions or day_key not in compat_data:
                        continue
                    
                    # Busca objeto da próxima atração
                    next_attr = next((a for a in available_attractions if a.name == next_attr_name), None)
                    if not next_attr:
                        continue
                    
                    # Modos válidos para ir à próxima atração
                    valid_to_modes = compat_data[day_key]
                    
                    # IMPORTANTE: Verifica se há caminho de volta ao hotel da próxima atração
                    has_return_path = False
                    if (next_attr_name in self._attraction_hotel_compatibility and 
                        hotel_name in self._attraction_hotel_compatibility[next_attr_name]):
                        has_return_path = len(self._attraction_hotel_compatibility[next_attr_name][hotel_name]) > 0
                    
                    # Só adiciona se há caminho de volta
                    if has_return_path:
                        for to_mode in valid_to_modes:
                            candidates.append({
                                "attraction": next_attr,
                                "to_mode": to_mode,
                            })
        
        return candidates
    
    def _get_valid_transport_modes(self, from_name: str, to_name: str) -> List[TransportMode]:
        """
        Obtém lista de modos de transporte válidos entre dois locais.
        
        Testa todos os modos disponíveis e retorna apenas os que têm tempo de viagem válido.
        
        Args:
            from_name: Nome do local de origem
            to_name: Nome do local de destino
            
        Returns:
            List[TransportMode]: Lista de modos válidos
        """
        from utils import Transport
        
        valid_modes = []
        for mode in [TransportMode.WALK, TransportMode.BUS_WALK, TransportMode.SUBWAY_WALK, TransportMode.CAR]:
            # Se tempo de viagem é válido (>= 0), modo é válido
            if Transport.get_travel_time(from_name, to_name, mode) >= 0:
                valid_modes.append(mode)
        
        return valid_modes
    
    def _choose_preferred_mode(self, valid_modes: List[TransportMode]) -> TransportMode:
        """
        Escolhe o modo de transporte preferido entre os válidos.
        
        Ordem de preferência:
        1. WALK (mais saudável, sem custo)
        2. SUBWAY_WALK (rápido, custo fixo)
        3. BUS_WALK (médio, custo fixo)
        4. CAR (mais caro, poluente)
        
        Args:
            valid_modes: Lista de modos válidos
            
        Returns:
            TransportMode: Modo preferido
        """
        if not valid_modes:
            return TransportMode.CAR  # Fallback
        
        # Ordem de preferência
        if TransportMode.WALK in valid_modes:
            return TransportMode.WALK
        
        if TransportMode.SUBWAY_WALK in valid_modes:
            return TransportMode.SUBWAY_WALK
        
        if TransportMode.BUS_WALK in valid_modes:
            return TransportMode.BUS_WALK
        
        if TransportMode.CAR in valid_modes:
            return TransportMode.CAR
        
        # Se chegou aqui, retorna o primeiro disponível
        return valid_modes[0]
