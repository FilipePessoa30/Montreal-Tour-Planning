# -*- coding: utf-8 -*-
"""
Versão comentada linha a linha de models.py.
Objetivo: explicar cada campo, método e validação das entidades do domínio.
A lógica foi preservada; apenas comentários foram adicionados.
"""

from dataclasses import dataclass  # Facilita a criação de classes de dados imutáveis/mutáveis
from typing import List, Dict, Tuple, Optional, Set  # Tipagem estática opcional
from enum import Enum  # Enumerações para tipos/constantes
from functools import lru_cache  # Cache de resultados de funções puras


class TransportMode(Enum):  # Enum de modos de transporte
    WALK = 0  # Caminhada
    SUBWAY_WALK = 1  # Metrô + caminhada
    BUS_WALK = 2  # Ônibus + caminhada
    CAR = 3  # Carro

    @staticmethod
    def get_mode_string(mode) -> str:  # Converte enum em string amigável
        mode_strings = {
            TransportMode.WALK: "Walking",
            TransportMode.SUBWAY_WALK: "Subway",
            TransportMode.BUS_WALK: "Bus",
            TransportMode.CAR: "Car"
        }
        return mode_strings.get(mode, "Unknown")  # Retorna nome ou "Unknown"


class LocationType(Enum):  # Tipo de ponto nos TimeInfo
    HOTEL = 0  # Hotel
    ATTRACTION = 1  # Atração


@dataclass
class TimeInfo:  # Registro de tempos por parada/visita
    location_type: LocationType  # Tipo do local (hotel/atração)
    arrival_time: float  # Minutos desde 00:00 em que chega
    wait_time: float  # Tempo de espera (ex: aguardar abertura)
    departure_time: float  # Minutos desde 00:00 em que parte

    @staticmethod
    def format_time(time_in_minutes: float) -> str:  # Formata minutos em HH:MM
        hours = int(time_in_minutes // 60)  # Horas inteiras
        minutes = int(time_in_minutes % 60)  # Minutos restantes
        return f"{hours:02d}:{minutes:02d}"  # String com zero à esquerda


@dataclass
class Hotel:  # Dados de hotel
    name: str  # Nome
    price: float  # Preço/diária
    rating: float  # Nota (0..5)
    latitude: float = 0.0  # Latitude (opcional)
    longitude: float = 0.0  # Longitude (opcional)

    def __post_init__(self):  # Validações após construção
        if self.price < 0:
            raise ValueError("Hotel price cannot be negative")
        if self.rating < 0 or self.rating > 5:
            raise ValueError("Hotel rating must be between 0 and 5")


@dataclass
class Attraction:  # Dados de uma atração
    name: str  # Nome
    neighborhood: str  # Bairro/Região
    visit_time: int  # Tempo típico de visita (minutos)
    cost: float  # Custo da atração
    saturday_opening_time: int  # Abertura sábado (minutos desde 00:00, -1 se fechado)
    saturday_closing_time: int  # Fechamento sábado
    sunday_opening_time: int  # Abertura domingo
    sunday_closing_time: int  # Fechamento domingo
    rating: float  # Nota (0..5)
    latitude: float = 0.0  # Coordenadas opcionais
    longitude: float = 0.0

    def __post_init__(self):  # Valida campos numéricos e horários
        if self.visit_time < 0:
            raise ValueError("Visit time cannot be negative")
        if self.cost < 0:
            raise ValueError("Cost cannot be negative")
        if self.rating < 0 or self.rating > 5:
            raise ValueError("Rating must be between 0 and 5")

        for time_val in [self.saturday_opening_time, self.saturday_closing_time,
                         self.sunday_opening_time, self.sunday_closing_time]:
            if time_val != -1 and (time_val < 0 or time_val >= 24*60):  # 0..1439 válido
                raise ValueError(f"Invalid time value: {time_val}")

    def __hash__(self):  # Permite uso em sets/dicts (identidade por nome)
        return hash(self.name)

    def __eq__(self, other):  # Igualdade por nome
        if not isinstance(other, Attraction):
            return False
        return self.name == other.name

    @lru_cache(maxsize=100)
    def is_open_at(self, time: int, is_saturday: bool) -> bool:  # Verifica se aberta em um horário específico
        opening_time = self.saturday_opening_time if is_saturday else self.sunday_opening_time
        closing_time = self.saturday_closing_time if is_saturday else self.sunday_closing_time

        if opening_time == -1 or closing_time == -1:  # -1 significa fechada o dia inteiro
            return False

        if opening_time == 0 and closing_time == 23 * 60 + 59:  # 24h aberta
            return True

        return opening_time <= time < closing_time  # Aberta entre abertura e fechamento

    @lru_cache(maxsize=2)
    def is_open_on_day(self, is_saturday: bool) -> bool:  # Aberta em algum horário no dia?
        opening_time = self.saturday_opening_time if is_saturday else self.sunday_opening_time
        closing_time = self.saturday_closing_time if is_saturday else self.sunday_closing_time
        return opening_time != -1 and closing_time != -1

    def get_opening_time(self, is_saturday: bool) -> int:  # Retorna horário de abertura
        return self.saturday_opening_time if is_saturday else self.sunday_opening_time

    def get_closing_time(self, is_saturday: bool) -> int:  # Retorna horário de fechamento
        return self.saturday_closing_time if is_saturday else self.sunday_closing_time


class DailyRoute:  # Roteiro de um dia (sábado ou domingo)
    def __init__(self, is_saturday: bool):  # Construtor
        self.is_saturday = is_saturday  # Flag do dia
        self.hotel = None  # Hotel associado
        self.attractions: List[Attraction] = []  # Lista de atrações sequenciais
        self.transport_modes: List[TransportMode] = []  # Modos hotel->a1, a1->a2, ..., aN->hotel
        self.return_to_hotel_mode: Optional[TransportMode] = None  # Não usado no original, mantido
        self.time_info: List[TimeInfo] = []  # Informações de tempo por ponto
        self.start_time = 8 * 60  # Hora inicial (8:00)
        self.end_time = 20 * 60  # Hora final (20:00)

        self._attraction_compatibility_cache = {}  # Cache de viabilidade de adição

    def set_hotel(self, hotel: Hotel):  # Define o hotel e invalida tempos
        if hotel is None:
            raise ValueError("Hotel pointer cannot be null")
        self.hotel = hotel
        self.recalculate_time_info()  # Recalcula tempos porque origem muda

        self._attraction_compatibility_cache.clear()  # Limpa cache pois contexto mudou

    def get_attractions(self) -> List[Attraction]:  # Retorna lista de atrações
        return self.attractions

    def get_transport_modes(self) -> List[TransportMode]:  # Retorna lista de modos incluindo retorno ao hotel
        """
        Get all transport modes including return to hotel mode.
        """
        if not self.attractions:  # Sem atrações, sem segmentos
            return []

        result = self.transport_modes.copy()  # Copia lista atual (pode incluir retorno já no final)
        if self.return_to_hotel_mode is not None:  # Se houver modo explícito de retorno, anexa
            result.append(self.return_to_hotel_mode)
        return result

    def get_time_info(self) -> List[TimeInfo]:  # Retorna estrutura de tempos
        return self.time_info

    def get_num_attractions(self) -> int:  # Contagem de atrações
        return len(self.attractions)

    def get_total_time(self) -> float:  # Tempo total do dia (minutos)
        """Get total time of the route in minutes"""
        if not self.attractions or not self.hotel or not self.time_info or len(self.time_info) < 2:
            return 0.0

        return self.time_info[-1].arrival_time - self.time_info[0].departure_time  # Hotel->...->Hotel

    def get_total_travel_time(self) -> float:  # Tempo total de deslocamentos
        """Get total travel time in minutes"""
        travel_time = 0.0
        for i in range(len(self.time_info) - 1):  # Soma cada trecho (entre registros consecutivos)
            travel_time += (self.time_info[i+1].arrival_time -
                           self.time_info[i].departure_time -
                           self.time_info[i+1].wait_time)
        return travel_time

    def get_total_visit_time(self) -> float:  # Tempo total de visitas
        """Get total visit time in minutes"""
        return sum(attr.visit_time for attr in self.attractions)

    def get_total_wait_time(self) -> float:  # Tempo total de espera
        """Get total wait time in minutes"""
        return sum(info.wait_time for info in self.time_info)

    def get_total_cost(self) -> float:  # Custo total do dia
        """Get total cost of the route in CAD"""
        from utils import Transport, Config  # Import tardio para evitar ciclos

        total_cost = sum(attr.cost for attr in self.attractions)  # Soma custos das atrações

        if self.hotel and self.attractions:  # Se tem hotel e pelo menos uma atração
            if self.transport_modes and len(self.transport_modes) > 0 and self.transport_modes[0] == TransportMode.CAR:
                travel_time = Transport.get_travel_time(
                    self.hotel.name, self.attractions[0].name, TransportMode.CAR)
                if travel_time > 0:
                    total_cost += travel_time * Config.CAR_COST_PER_MINUTE  # Custo por minuto de carro

            for i in range(len(self.attractions) - 1):  # Entre atrações consecutivas
                if i+1 < len(self.transport_modes) and self.transport_modes[i+1] == TransportMode.CAR:
                    travel_time = Transport.get_travel_time(
                        self.attractions[i].name, self.attractions[i+1].name, TransportMode.CAR)
                    if travel_time > 0:
                        total_cost += travel_time * Config.CAR_COST_PER_MINUTE

            if len(self.transport_modes) > len(self.attractions):  # Segmento de retorno presente?
                return_mode = self.transport_modes[len(self.attractions)]
                if return_mode == TransportMode.CAR:
                    travel_time = Transport.get_travel_time(
                        self.attractions[-1].name, self.hotel.name, TransportMode.CAR)
                    if travel_time > 0:
                        total_cost += travel_time * Config.CAR_COST_PER_MINUTE

        return total_cost  # Retorna custo final

    def get_total_rating(self) -> float:  # Soma das notas das atrações
        """Get sum of attraction ratings"""
        if not self.attractions:
            return 0.0
        return sum(attr.rating for attr in self.attractions)

    def get_neighborhoods(self) -> Set[str]:  # Conjunto de bairros visitados
        """Get unique neighborhoods visited"""
        return {attr.neighborhood for attr in self.attractions}

    def can_add_attraction(self, attraction: Attraction, mode: TransportMode) -> Tuple[bool, float, float]:  # Verifica viabilidade de inserção no fim
        """
        Check if an attraction can be feasibly added to the route

        Args:
            attraction: The attraction to check
            mode: Transport mode for reaching this attraction from the previous location

        Returns:
            (is_feasible, arrival_time, departure_time)
        """
        from utils import Transport  # Import local

        if not self.hotel:  # Sem hotel definido, rota inválida
            return False, 0, 0

        cache_key = (attraction.name, mode.value)  # Chave simplificada de cache
        if cache_key in self._attraction_compatibility_cache:  # Retorna de cache se disponível
            return self._attraction_compatibility_cache[cache_key]

        if not self.attractions:  # Primeira atração: parte do hotel no start_time
            current_time = self.start_time
            from_name = self.hotel.name
        else:  # Caso já tenha atrações
            if len(self.time_info) <= len(self.attractions):  # Garante time_info válido/atualizado
                self.recalculate_time_info()
                if not self.time_info or len(self.time_info) <= len(self.attractions):  # Segurança
                    self._attraction_compatibility_cache[cache_key] = (False, 0, 0)
                    return False, 0, 0

            current_time = self.time_info[len(self.attractions)].departure_time  # Hora de saída do último ponto
            from_name = self.attractions[-1].name  # Origem é última atração

        travel_time = Transport.get_travel_time(from_name, attraction.name, mode)  # Tempo até a nova atração

        if travel_time < 0:  # Sem trajeto válido
            self._attraction_compatibility_cache[cache_key] = (False, 0, 0)
            return False, 0, 0

        current_time += travel_time  # Chega na atração

        if not attraction.is_open_on_day(self.is_saturday):  # Se fechada nesse dia
            self._attraction_compatibility_cache[cache_key] = (False, 0, 0)
            return False, 0, 0

        opening_time = attraction.get_opening_time(self.is_saturday)  # Abertura
        closing_time = attraction.get_closing_time(self.is_saturday)  # Fechamento

        if current_time < opening_time:  # Se chega antes de abrir, espera
            current_time = opening_time

        arrival_time = current_time  # Hora final de chegada

        if current_time >= closing_time:  # Chegou depois de fechar
            self._attraction_compatibility_cache[cache_key] = (False, 0, 0)
            return False, 0, 0

        visit_end_time = current_time + attraction.visit_time  # Saída após visita

        if visit_end_time > closing_time:  # Estourou fechamento
            self._attraction_compatibility_cache[cache_key] = (False, 0, 0)
            return False, 0, 0

        if visit_end_time > self.end_time:  # Estourou fim do dia
            self._attraction_compatibility_cache[cache_key] = (False, 0, 0)
            return False, 0, 0

        departure_time = visit_end_time  # Hora de saída

        result = (True, arrival_time, departure_time)  # Resultado final
        self._attraction_compatibility_cache[cache_key] = result  # Cacheia
        return result

    def add_attraction(self, attraction: Attraction, mode: TransportMode) -> bool:  # Adiciona atração ao fim
        """
        Add an attraction to the route with the specified transport mode.
        This method does NOT set the return mode to hotel - that should
        be done separately.

        Args:
            attraction: The attraction to add
            mode: Transport mode for reaching this attraction from the previous location

        Returns:
            True if added successfully, False otherwise
        """
        if not self.hotel:
            raise ValueError("Cannot add attraction to route without a hotel")

        is_feasible, arrival_time, departure_time = self.can_add_attraction(attraction, mode)  # Checa viabilidade

        if not is_feasible:  # Se não pode, aborta
            return False

        self.attractions.append(attraction)  # Acrescenta atração

        self.transport_modes.append(mode)  # Acrescenta modo do segmento até essa atração

        if len(self.attractions) == 1:  # Se é a primeira atração, garante um modo de retorno placeholder (CAR)
            self.transport_modes.append(TransportMode.CAR)

        self.recalculate_time_info()  # Recalcula tempos

        if not self.is_valid():  # Se ficou inválida, desfaz
            self.attractions.pop()
            if len(self.transport_modes) == 2 and len(self.attractions) == 0:
                self.transport_modes = []  # Remove ambos (ida e retorno placeholder)
            else:
                self.transport_modes.pop()  # Remove último modo
            self.recalculate_time_info()
            return False

        self._attraction_compatibility_cache.clear()  # Limpa cache pois mudou estado

        return True  # Sucesso

    def set_return_mode(self, mode: TransportMode) -> bool:  # Define modo do último segmento (última atração->hotel)
        """
        Set the transport mode for returning from the last attraction to the hotel.
        This should be called only after all attractions have been added.

        Args:
            mode: Transport mode for returning to hotel

        Returns:
            True if the mode is valid, False otherwise
        """
        from utils import Transport  # Import local

        if not self.hotel or not self.attractions:  # Precisa ter hotel e atração
            return False

        old_mode = self.transport_modes[-1] if len(self.transport_modes) > len(self.attractions) else None  # Guarda antigo

        if len(self.transport_modes) > len(self.attractions):  # Já havia modo de retorno
            self.transport_modes[-1] = mode  # Substitui
        else:
            self.transport_modes.append(mode)  # Adiciona modo de retorno

        self.recalculate_time_info()  # Recalcula tempos

        if not self.is_valid():  # Se inválido com novo modo, desfaz
            if old_mode is not None:
                self.transport_modes[-1] = old_mode
            else:
                if len(self.transport_modes) > len(self.attractions):
                    self.transport_modes.pop()

            self.recalculate_time_info()
            return False

        return True  # Válido

    def get_valid_return_modes(self) -> List[TransportMode]:  # Lista modos válidos para retorno ao hotel
        """
        Get all valid transport modes for returning from the last attraction to the hotel

        Returns:
            List of valid transport modes in order of preference (fastest first)
        """
        from utils import Transport  # Import local

        if not self.hotel or not self.attractions:  # Precisa de hotel e pelo menos uma atração
            return []

        valid_modes = []  # Lista final de modos

        if len(self.time_info) <= len(self.attractions):  # Garante time_info atualizado
            self.recalculate_time_info()
            if not self.time_info or len(self.time_info) <= len(self.attractions):  # Se ainda inválido
                return []

        last_departure_time = self.time_info[len(self.attractions)].departure_time  # Hora de saída da última atração

        mode_times = []  # Pares (modo, tempo)
        for mode in [TransportMode.WALK, TransportMode.BUS_WALK,
                     TransportMode.SUBWAY_WALK, TransportMode.CAR]:  # Testa todos os modos
            travel_time = Transport.get_travel_time(
                self.attractions[-1].name, self.hotel.name, mode)

            if travel_time < 0:  # Sem matriz/ligação para este modo
                continue

            if last_departure_time + travel_time <= self.end_time:  # Cabe no dia?
                mode_times.append((mode, travel_time))

        if not mode_times:  # Nenhum modo cabe
            return []

        valid_modes = []  # Lista para ordenação por preferência heurística
        for mode, time in mode_times:
            weight = 0  # Peso base por modo (heurística)
            if mode == TransportMode.WALK:
                weight = 20
            elif mode == TransportMode.SUBWAY_WALK:
                weight = 40
            elif mode == TransportMode.BUS_WALK:
                weight = 30
            else:
                weight = 10

            time_factor = min(1.0, 10/time) if time > 0 else 0.1  # Fator baseado no tempo (mais rápido => maior)

            combined_weight = weight * time_factor  # Combina

            valid_modes.append((mode, combined_weight))  # Empilha

        valid_modes.sort(key=lambda x: x[1], reverse=True)  # Ordena por peso desc

        valid_modes = [mode for mode, _ in valid_modes]  # Mantém apenas modos ordenados

        return valid_modes  # Retorna lista preferencial

    def recalculate_time_info(self):  # Recalcula toda a linha do tempo do dia
        """Recalculate all time information for the route"""
        from utils import Transport  # Import local

        if not self.hotel:  # Sem hotel, zera time_info
            self.time_info = []
            return

        temp_time_info = [None] * (len(self.attractions) + 2)  # Estrutura temporária (hotel início + N atrações + hotel fim)

        current_time = self.start_time  # Começa no horário inicial do dia

        temp_time_info[0] = TimeInfo(  # Registro do hotel de saída
            location_type=LocationType.HOTEL,
            arrival_time=current_time,
            wait_time=0,
            departure_time=current_time
        )

        for i, attraction in enumerate(self.attractions):  # Para cada atração na ordem
            if i >= len(self.transport_modes):  # Segurança: falta modo correspondente
                return

            mode = self.transport_modes[i]  # Modo do segmento até esta atração

            if i == 0:  # Origem do primeiro segmento é o hotel
                from_name = self.hotel.name
            else:  # Demais, origem é a atração anterior
                from_name = self.attractions[i-1].name

            travel_time = Transport.get_travel_time(from_name, attraction.name, mode)  # Tempo de deslocamento

            if travel_time < 0:  # Sem ligação
                return

            current_time += travel_time  # Chegada prevista

            if not attraction.is_open_on_day(self.is_saturday):  # Se fechada no dia
                return

            opening_time = attraction.get_opening_time(self.is_saturday)  # Abertura
            closing_time = attraction.get_closing_time(self.is_saturday)  # Fechamento

            wait_time = 0.0  # Tempo de espera calculado

            if current_time < opening_time:  # Se chegou antes de abrir
                wait_time = opening_time - current_time  # Espera até abrir
                current_time = opening_time

            if current_time >= closing_time:  # Se chegou depois de fechar
                return

            temp_time_info[i+1] = TimeInfo(  # Registra tempos desta atração
                location_type=LocationType.ATTRACTION,
                arrival_time=current_time,
                wait_time=wait_time,
                departure_time=current_time + attraction.visit_time
            )

            current_time += attraction.visit_time  # Atualiza tempo após visita

            if current_time > closing_time:  # Se passou do fechamento
                return

        if self.attractions:  # Se há pelo menos uma atração, considera retorno ao hotel
            if len(self.transport_modes) <= len(self.attractions):  # Falta modo de retorno
                return

            mode = self.transport_modes[len(self.attractions)]  # Modo do segmento de retorno

            travel_time = Transport.get_travel_time(
                self.attractions[-1].name, self.hotel.name, mode)  # Tempo do último trecho

            if travel_time < 0:  # Sem ligação
                return

            current_time += travel_time  # Chega ao hotel

            if current_time > self.end_time:  # Passou do horário de término do dia
                return

            temp_time_info[-1] = TimeInfo(  # Registra chegada final ao hotel
                location_type=LocationType.HOTEL,
                arrival_time=current_time,
                wait_time=0,
                departure_time=current_time
            )

        if all(entry is not None for entry in temp_time_info):  # Se todos registros foram preenchidos
            self.time_info = temp_time_info  # Confirma estrutura
        else:
            self.time_info = []  # Caso contrário, invalida

    def is_valid(self) -> bool:  # Verifica consistência/viabilidade do dia
        """Check if the route is valid (respects all constraints)"""
        if not self.hotel:  # Sem hotel, inválido
            return False

        if not self.attractions:  # Sem atrações é considerado válido (rota vazia do dia)
            return True

        if not self.time_info:  # Sem info de tempo, inválido
            return False

        if len(self.time_info) != len(self.attractions) + 2:  # Estrutura deve ser hotel + N + hotel
            return False

        for i, attraction in enumerate(self.attractions):  # Checa cada atração
            if not attraction.is_open_on_day(self.is_saturday):  # Deve estar aberta no dia
                return False

            info = self.time_info[i+1]  # Registro de tempo da atração
            if not info:
                return False

            opening_time = attraction.get_opening_time(self.is_saturday)
            closing_time = attraction.get_closing_time(self.is_saturday)

            if info.arrival_time < opening_time or info.arrival_time >= closing_time:  # Chegada dentro da janela
                return False

            if info.departure_time > closing_time:  # Saída não pode passar do fechamento
                return False

        if self.time_info[-1].arrival_time > self.end_time:  # Chegada final não pode exceder horário limite
            return False

        return True  # Tudo ok


class Solution:  # Agrega os dois dias + hotel e calcula objetivos
    def __init__(self, hotel: Hotel, day1_route: DailyRoute, day2_route: DailyRoute):
        self.hotel = hotel  # Hotel escolhido
        self.day1_route = day1_route  # Rota de sábado
        self.day2_route = day2_route  # Rota de domingo
        self.objectives = self.calculate_objectives()  # Pré-calcula objetivos

    def get_objectives(self) -> List[float]:  # Retorna vetor de objetivos
        return self.objectives

    def calculate_objectives(self) -> List[float]:  # Calcula os quatro objetivos
        """
        Calculate the objectives:
        F1: Maximize number of attractions visited
        F2: Maximize total quality (ratings)
        F3: Minimize total time
        F4: Minimize total cost
        """
        total_attractions = self.day1_route.get_num_attractions() + self.day2_route.get_num_attractions()  # F1

        total_rating = self.day1_route.get_total_rating() + self.day2_route.get_total_rating()  # F2 base
        if self.hotel:
            total_rating += self.hotel.rating * 2  # Bônus do hotel na qualidade
        if total_attractions == 0:
            total_rating = 0.0  # Se não visita nada, qualidade 0

        total_time = self.day1_route.get_total_time() + self.day2_route.get_total_time()  # F3 (minimizar)

        total_cost = self.day1_route.get_total_cost() + self.day2_route.get_total_cost()  # F4 base
        if self.hotel:
            total_cost += self.hotel.price  # Soma preço do hotel

        return [  # Retorna vetor dos quatro objetivos
            total_attractions,
            total_rating,
            total_time,
            total_cost
        ]

    def has_overlapping_attractions(self) -> bool:  # Verifica atrações repetidas entre os dias
        """Check if two daily routes have overlapping attractions"""
        day1_attractions = {attr.name for attr in self.day1_route.get_attractions()}  # Conjunto nomes dia 1

        for attr in self.day2_route.get_attractions():  # Percorre dia 2
            if attr.name in day1_attractions:  # Encontrou repetição
                return True

        return False  # Sem sobreposição

    def check_mandatory_attractions(self, mandatory_attractions: List[Attraction]) -> bool:  # Checa obrigatórias primeiras
        """Check if mandatory attractions are included as first attractions of each day"""
        if mandatory_attractions and self.day1_route.get_attractions():  # Se há obrigatória para dia 1
            if self.day1_route.get_attractions()[0] != mandatory_attractions[0]:  # E não está como primeira
                return False

        if len(mandatory_attractions) > 1 and self.day2_route.get_attractions():  # Idem para dia 2
            if self.day2_route.get_attractions()[0] != mandatory_attractions[1]:
                return False

        return True  # Ok
