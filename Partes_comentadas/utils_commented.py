"""
Arquivo utilitário comentado linha a linha.
Repete a lógica de utils.py, adicionando explicações passo a passo sem alterar comportamento.
"""

# Importa módulos padrão necessários
import csv  # (não utilizado neste módulo, mas mantido por compatibilidade)
import re   # Regex para normalização de strings
import os   # Operações de sistema de arquivos
from typing import Dict, List, Tuple, Set, Optional, Any  # Tipagem estática

# Bibliotecas de terceiros
import pandas as pd  # (não utilizada diretamente aqui; mantida para compatibilidade)

# Importa modelos e enums do domínio
from models import Hotel, Attraction, TransportMode

# Cache LRU para funções de normalização de string
from functools import lru_cache


# Classe de configuração com constantes usadas no projeto
class Config:
    # Tempo limite de um dia de passeio (em minutos)
    DAILY_TIME_LIMIT = 12 * 60
    # Preferência de tempo máximo para optar por caminhar (min)
    WALK_TIME_PREFERENCE = 20.0
    # Custo por minuto quando o modo de transporte é CARRO
    CAR_COST_PER_MINUTE = 1.0
    # Tolerância genérica para comparações
    TOLERANCE = 0.05


# Estruturas estáticas que armazenam as matrizes de transporte e metadados
class TransportMatrices:
    # Matrizes atracção->atração para cada modo (índice = TransportMode.value)
    attraction_to_attraction_times = [[] for _ in range(4)]
    
    # Matrizes hotel->atração para cada modo
    hotel_to_attraction_times = [[] for _ in range(4)]
    
    # Matrizes atração->hotel para cada modo
    attraction_to_hotel_times = [[] for _ in range(4)]
    
    # Mapas de nome normalizado para índice nas listas de nomes
    attraction_indices: Dict[str, int] = {}
    hotel_indices: Dict[str, int] = {}
    
    # Listas de nomes (na ordem das matrizes)
    attraction_names: List[str] = []
    hotel_names: List[str] = []
    
    # Conjuntos para checagens rápidas de presença
    attraction_name_set: Set[str] = set()
    hotel_name_set: Set[str] = set()
    
    # Flag que indica se as matrizes foram carregadas
    matrices_loaded = False


# Função para normalizar strings, com cache para acelerar chamadas repetidas
@lru_cache(maxsize=1000)
def normalize_string(s: str) -> str:
    # Se a string for vazia/None, retorna vazio
    if not s:
        return ""
    
    # Converte para minúsculas
    result = s.lower()
    
    # Substitui qualquer caractere não alfanumérico/espaço por espaço
    result = re.sub(r'[^\w\s]', ' ', result)
    
    # Colapsa múltiplos espaços em apenas um
    result = re.sub(r'\s+', ' ', result)
    
    # Remove espaços do início/fim
    result = result.strip()
    
    # Retorna string normalizada
    return result


# Heurística para decidir se um nome se refere a um hotel
def is_hotel(name: str) -> bool:
    # Se o nome existir exatamente no conjunto de hotéis, é hotel
    if name in TransportMatrices.hotel_name_set:
        return True
    
    # Normaliza o nome e compara com nomes de hotéis normalizados (match exato)
    normalized = normalize_string(name)
    for hotel_name in TransportMatrices.hotel_names:
        if normalized == normalize_string(hotel_name):
            return True
    
    # Heurística: se um nome contiver o outro (após normalização), considerar como hotel
    for hotel_name in TransportMatrices.hotel_names:
        norm_hotel = normalize_string(hotel_name)
        if norm_hotel in normalized or normalized in norm_hotel:
            return True
    
    # Se aparecer explicitamente como atração conhecida, então não é hotel
    if name in TransportMatrices.attraction_name_set:
        return False
    
    # Se for igual (normalizado) a alguma atração, não é hotel
    for attr_name in TransportMatrices.attraction_names:
        if normalized == normalize_string(attr_name):
            return False
    
    # Lista de palavras indicadoras de hotel
    hotel_indicators = [
        "hotel", "hôtel", "auberge", "inn", "suites", "hostel",
        "marriott", "hilton", "sheraton", "westin", "hyatt", "fairmont"
    ]
    
    # Se alguma palavra do nome normalizado estiver entre os indicadores, assume hotel
    words = normalized.split()
    for word in words:
        if word in hotel_indicators:
            return True
    
    # Caso nenhuma regra se aplique, assume que não é hotel
    return False


# Constrói conjuntos para membership rápido, a partir das listas
def create_entity_sets():
    # Converte listas em sets para lookups O(1)
    TransportMatrices.hotel_name_set = set(TransportMatrices.hotel_names)
    TransportMatrices.attraction_name_set = set(TransportMatrices.attraction_names)
    
    # Log simples para diagnóstico
    print(
        f"Created entity sets with {len(TransportMatrices.hotel_name_set)} hotels and "
        f"{len(TransportMatrices.attraction_name_set)} attractions"
    )


# Constrói dicionários de nomes normalizados para índices (facilitam buscas)
def create_name_mappings():
    # Garante que matrizes foram carregadas
    if not TransportMatrices.matrices_loaded:
        print("Error: transport matrices not loaded before creating mappings.")
        return
    
    # Limpa índices anteriores
    TransportMatrices.attraction_indices.clear()
    TransportMatrices.hotel_indices.clear()
    
    # Mapeia atrações com diferentes chaves normalizadas
    for i, name in enumerate(TransportMatrices.attraction_names):
        normalized = normalize_string(name)
        TransportMatrices.attraction_indices[normalized] = i
        no_spaces = normalized.replace(" ", "")
        TransportMatrices.attraction_indices[no_spaces] = i
    
    # Mapeia hotéis com diferentes chaves normalizadas + variação sem a primeira palavra
    for i, name in enumerate(TransportMatrices.hotel_names):
        normalized = normalize_string(name)
        TransportMatrices.hotel_indices[normalized] = i
        no_spaces = normalized.replace(" ", "")
        TransportMatrices.hotel_indices[no_spaces] = i
        
        # Se o nome começar com "hotel/hôtel/auberge", adiciona um alias sem a primeira palavra
        words = normalized.split()
        if len(words) > 1 and words[0] in ["hotel", "hôtel", "auberge"]:
            first_word_removed = ' '.join(words[1:])
            TransportMatrices.hotel_indices[first_word_removed] = i
    
    # Recria conjuntos de nomes para lookups rápidos
    create_entity_sets()
    
    # Log de quantidades mapeadas
    print(
        f"Name mappings created for {len(TransportMatrices.attraction_names)} attractions and "
        f"{len(TransportMatrices.hotel_names)} hotels."
    )


# Tenta resolver o nome original para o nome usado nas matrizes (tratando grafias)
def find_matrix_name(original_name: str, is_hotel: bool = False) -> str:
    # Tratamento especial para Place d'Armes (várias grafias)
    if "place d'armes" in original_name.lower() or "place darmes" in original_name.lower():
        return "Place d'Armes"
        
    # Normaliza o nome para comparação
    normalized_name = normalize_string(original_name)
    
    # Busca match exato (normalizado) em hotéis
    if is_hotel:
        for hotel_name in TransportMatrices.hotel_names:
            if normalized_name == normalize_string(hotel_name):
                return hotel_name
    else:
        # Busca match exato (normalizado) em atrações
        for attr_name in TransportMatrices.attraction_names:
            if normalized_name == normalize_string(attr_name):
                return attr_name
    
    # Caso não encontre, retorna o original (sem alterar)
    return original_name


# Retorna o índice de uma atração pelo nome; -1 se não encontrado
def find_attraction_index(name: str) -> int:
    # Se o nome for de hotel, não há índice de atração
    if is_hotel(name):
        return -1
    
    # Normaliza o nome
    normalized = normalize_string(name)
    
    # Tenta lookup direto no mapa
    if normalized in TransportMatrices.attraction_indices:
        return TransportMatrices.attraction_indices[normalized]
    
    # Tenta sem espaços
    no_spaces = normalized.replace(" ", "")
    if no_spaces in TransportMatrices.attraction_indices:
        return TransportMatrices.attraction_indices[no_spaces]
    
    # Tenta por inclusão mútua (nome contém/é contido)
    for attr_name in TransportMatrices.attraction_names:
        norm_attr = normalize_string(attr_name)
        if normalized in norm_attr or norm_attr in normalized:
            return TransportMatrices.attraction_indices[norm_attr]
    
    # Se nada funcionar, retorna -1
    return -1


# Retorna o índice de um hotel pelo nome; -1 se não encontrado
def find_hotel_index(name: str) -> int:
    # Se o nome não for de hotel, retorna -1
    if not is_hotel(name):
        return -1
    
    # Normaliza o nome
    normalized = normalize_string(name)
    
    # Tenta lookup direto no mapa
    if normalized in TransportMatrices.hotel_indices:
        return TransportMatrices.hotel_indices[normalized]
    
    # Tenta sem espaços
    no_spaces = normalized.replace(" ", "")
    if no_spaces in TransportMatrices.hotel_indices:
        return TransportMatrices.hotel_indices[no_spaces]
    
    # Tenta remover a primeira palavra (hotel/hôtel/auberge)
    words = normalized.split()
    if len(words) > 1 and words[0] in ["hotel", "hôtel", "auberge"]:
        first_word_removed = ' '.join(words[1:])
        if first_word_removed in TransportMatrices.hotel_indices:
            return TransportMatrices.hotel_indices[first_word_removed]
    
    # Tenta por inclusão mútua
    for hotel_name in TransportMatrices.hotel_names:
        norm_hotel = normalize_string(hotel_name)
        if normalized in norm_hotel or norm_hotel in normalized:
            return TransportMatrices.hotel_indices[norm_hotel]
    
    # Se nada funcionar, retorna -1
    return -1


# Classe com utilitários de transporte (tempos, custos e modos)
class Transport:
    
    # Cache de tempos de deslocamento por (origem, destino, modo)
    _travel_time_cache = {}
    
    # Cache de modos válidos por par (origem, destino)
    _mode_compatibility_cache = {}
    
    @staticmethod
    def get_distance(from_name: str, to_name: str, mode: TransportMode) -> float:
        # A distância é estimada como tempo(min) * 20 (heurística simples)
        return Transport.get_travel_time(from_name, to_name, mode) * 20
    
    @staticmethod
    def get_travel_time(from_name: str, to_name: str, mode: TransportMode) -> float:
        # Garante que as matrizes estão carregadas
        if not TransportMatrices.matrices_loaded:
            raise RuntimeError("Transport matrices not loaded. Call load_transport_matrices first.")
        
        # Monta chave de cache
        cache_key = (from_name, to_name, mode.value)
        # Retorna do cache se possível
        if cache_key in Transport._travel_time_cache:
            return Transport._travel_time_cache[cache_key]
        
        # Tratamento especial para Place d'Armes (tempo fixo)
        if "Place d'Armes" in from_name or "Place d'Armes" in to_name:
            Transport._travel_time_cache[cache_key] = 15.0
            return 15.0
            
        # Decide tipos (hotel/atração) das pontas
        from_is_hotel = is_hotel(from_name)
        to_is_hotel = is_hotel(to_name)
        
        # Seleciona a matriz apropriada conforme a combinação
        if from_is_hotel and to_is_hotel:
            result = -1.0  # não há deslocamento direto entre hotéis nas matrizes
        elif from_is_hotel and not to_is_hotel:
            result = Transport.get_hotel_to_attraction_time(from_name, to_name, mode)
        elif not from_is_hotel and to_is_hotel:
            result = Transport.get_attraction_to_hotel_time(from_name, to_name, mode)
        else:
            result = Transport.get_attraction_to_attraction_time(from_name, to_name, mode)
        
        # Armazena no cache e retorna
        Transport._travel_time_cache[cache_key] = result
        return result
    
    @staticmethod
    def get_attraction_to_attraction_time(from_name: str, to_name: str, mode: TransportMode) -> float:
        # Resolve índices nas matrizes
        from_idx = find_attraction_index(from_name)
        to_idx = find_attraction_index(to_name)
        
        # Se algum não for válido, retorna -1
        if from_idx == -1:
            return -1.0
        
        if to_idx == -1:
            return -1.0
        
        # Seleciona a matriz do modo
        mode_idx = mode.value
        matrix = TransportMatrices.attraction_to_attraction_times[mode_idx]
        
        # Valida limites
        if from_idx >= len(matrix) or to_idx >= len(matrix[from_idx]):
            return -1.0
        
        # Lê o valor da célula
        time = matrix[from_idx][to_idx]
        
        # Valores negativos significam indisponível
        if time < 0:
            return -1.0
        
        # Retorna tempo válido
        return time
    
    @staticmethod
    def get_hotel_to_attraction_time(from_name: str, to_name: str, mode: TransportMode) -> float:
        # Resolve índices de hotel e atração
        hotel_idx = find_hotel_index(from_name)
        attr_idx = find_attraction_index(to_name)
        
        # Valida presença
        if hotel_idx == -1:
            return -1.0
        
        if attr_idx == -1:
            return -1.0
        
        # Seleciona matriz do modo
        mode_idx = mode.value
        matrix = TransportMatrices.hotel_to_attraction_times[mode_idx]
        
        # Valida limites
        if hotel_idx >= len(matrix) or attr_idx >= len(matrix[hotel_idx]):
            return -1.0
        
        # Lê tempo
        time = matrix[hotel_idx][attr_idx]
        
        # Valores negativos significam indisponível
        if time < 0:
            return -1.0
        
        # Retorna tempo válido
        return time
    
    @staticmethod
    def get_attraction_to_hotel_time(from_name: str, to_name: str, mode: TransportMode) -> float:
        # Resolve índices de atração e hotel
        attr_idx = find_attraction_index(from_name)
        hotel_idx = find_hotel_index(to_name)
        
        # Valida presença
        if attr_idx == -1:
            return -1.0
        
        if hotel_idx == -1:
            return -1.0
        
        # Seleciona matriz do modo
        mode_idx = mode.value
        matrix = TransportMatrices.attraction_to_hotel_times[mode_idx]
        
        # Valida limites (nota: índice da matriz é por hotel na primeira dimensão)
        if hotel_idx >= len(matrix) or attr_idx >= len(matrix[hotel_idx]):
            return -1.0
        
        # Lê tempo (acesso [hotel][attr])
        time = matrix[hotel_idx][attr_idx]
        
        # Indisponível
        if time < 0:
            return -1.0
        
        # Valida tempo
        return time
    
    @staticmethod
    def get_travel_cost(from_name: str, to_name: str, mode: TransportMode) -> float:
        # Apenas CAR possui custo por minuto; demais modos custo 0
        if mode == TransportMode.CAR:
            return Transport.get_travel_time(from_name, to_name, mode) * Config.CAR_COST_PER_MINUTE
        else:
            return 0.0
    
    @staticmethod
    def get_valid_transport_modes(from_name: str, to_name: str) -> List[TransportMode]:
        # Usa cache por par origem-destino
        cache_key = (from_name, to_name)
        if cache_key in Transport._mode_compatibility_cache:
            return Transport._mode_compatibility_cache[cache_key]
        
        # Avalia cada modo e inclui os com tempo >= 0
        valid_modes = []
        for mode in [TransportMode.CAR, TransportMode.BUS_WALK, TransportMode.SUBWAY_WALK, TransportMode.WALK]:
            travel_time = Transport.get_travel_time(from_name, to_name, mode)
            if travel_time >= 0:
                valid_modes.append(mode)
        
        # Armazena no cache e retorna
        Transport._mode_compatibility_cache[cache_key] = valid_modes
        return valid_modes
    
    @staticmethod
    def determine_preferred_mode(from_name: str, to_name: str) -> TransportMode:
        # Obtém modos válidos
        valid_modes = Transport.get_valid_transport_modes(from_name, to_name)
        
        # Se não houver nenhum, escolhe CAR como fallback
        if not valid_modes:
            return TransportMode.CAR
        
        # Preferência por caminhar se tempo <= limiar
        if TransportMode.WALK in valid_modes:
            walk_time = Transport.get_travel_time(from_name, to_name, TransportMode.WALK)
            if walk_time <= Config.WALK_TIME_PREFERENCE:
                return TransportMode.WALK
        
        # Senão, prefere metrô, depois ônibus, depois o primeiro disponível
        if TransportMode.SUBWAY_WALK in valid_modes:
            return TransportMode.SUBWAY_WALK
        
        if TransportMode.BUS_WALK in valid_modes:
            return TransportMode.BUS_WALK
        
        return valid_modes[0]
    
    @staticmethod
    def format_time(minutes: float) -> str:
        # Converte minutos totais em HH:MM
        total_minutes = int(minutes)
        hours = total_minutes // 60
        mins = total_minutes % 60
        return f"{hours:02d}:{mins:02d}"


# Classe responsável por carregar dados de CSVs e matrizes de transporte
class Parser:
    
    @staticmethod
    def load_attractions(filename: str) -> List[Attraction]:
        # Lista que receberá objetos Attraction
        attractions = []
        
        # Abre arquivo CSV de atrações
        with open(filename, 'r', encoding='utf-8') as file:
            # Ignora a primeira linha (cabeçalho)
            next(file)
            
            # Processa linha a linha
            for line in file:
                # Pula linhas vazias ou comentários
                if not line.strip() or line.strip().startswith('#'):
                    continue
                
                # Parser simples de CSV com suporte a aspas
                fields = []
                current_field = ""
                in_quotes = False
                
                for char in line:
                    if char == '"':
                        in_quotes = not in_quotes
                        continue
                    if char == ',' and not in_quotes:
                        fields.append(current_field)
                        current_field = ""
                    else:
                        current_field += char
                
                # Anexa o último campo
                if current_field:
                    fields.append(current_field)
                
                # Remove espaços ao redor
                fields = [field.strip() for field in fields]
                
                # Espera pelo menos 10 campos de dados
                if len(fields) >= 10:
                    try:
                        # Extrai campos principais conforme layout esperado
                        name = fields[1]
                        neighborhood = fields[3]
                        
                        # Converte nota (rating) tratando vírgula
                        rating = 4.0
                        try:
                            rating_str = fields[5].replace(',', '.')
                            rating = float(rating_str)
                        except Exception as e:
                            raise ValueError(f"Invalid rating for {name}: {str(e)}")
                        
                        # Converte custo
                        cost = 0.0
                        try:
                            cost_str = fields[6].replace(',', '.')
                            cost = float(cost_str)
                        except Exception as e:
                            raise ValueError(f"Invalid cost for {name}: {str(e)}")
                        
                        # Horários de sábado (abertura/fechamento)
                        saturday_opening_time, saturday_closing_time = Parser._parse_opening_hours(fields[7])
                        
                        # Horários de domingo
                        sunday_opening_time, sunday_closing_time = Parser._parse_opening_hours(fields[8])
                        
                        # Tempo de visita (minutos)
                        visit_time = 60
                        try:
                            visit_time = int(fields[9])
                        except Exception as e:
                            raise ValueError(f"Invalid visit time for {name}: {str(e)}")
                        
                        # Instancia Attraction com os dados parseados
                        attraction = Attraction(
                            name=name,
                            neighborhood=neighborhood,
                            visit_time=visit_time,
                            cost=cost,
                            saturday_opening_time=saturday_opening_time,
                            saturday_closing_time=saturday_closing_time,
                            sunday_opening_time=sunday_opening_time,
                            sunday_closing_time=sunday_closing_time,
                            rating=rating
                        )
                        # Adiciona à lista
                        attractions.append(attraction)
                    except Exception as e:
                        # Loga erro específico da linha
                        print(f"Error processing attraction: {str(e)} in line: {line}")
                else:
                    # Loga aviso de linha malformada
                    print(f"Warning: CSV line has too few fields: {line}")
        
        # Falha se nada foi carregado
        if not attractions:
            raise RuntimeError(f"No valid attractions loaded from: {filename}")
        
        # Log de sucesso
        print(f"Loaded {len(attractions)} attractions.")
        return attractions
    
    @staticmethod
    def load_hotels(filename: str) -> List[Hotel]:
        # Lista de hotéis
        hotels = []
        
        # Abre CSV de hotéis
        with open(filename, 'r', encoding='utf-8') as file:
            # Ignora cabeçalho
            next(file)
            
            # Itera linhas do arquivo
            for line in file:
                # Pula vazias/comentadas
                if not line.strip() or line.strip().startswith('#'):
                    continue
                
                # Parser simples de CSV com aspas
                fields = []
                current_field = ""
                in_quotes = False
                
                for char in line:
                    if char == '"':
                        in_quotes = not in_quotes
                    elif char == ',' and not in_quotes:
                        fields.append(current_field)
                        current_field = ""
                    else:
                        current_field += char
                
                # Anexa o último campo
                fields.append(current_field)
                
                # Remove aspas envolvendo e espaços
                for i in range(len(fields)):
                    field = fields[i]
                    if len(field) >= 2 and field[0] == '"' and field[-1] == '"':
                        field = field[1:-1]
                    fields[i] = field.strip()
                
                # Valida quantidade mínima
                if len(fields) < 3:
                    print(f"Warning: CSV line has too few fields: {line}")
                    continue
                
                try:
                    # Nome do hotel
                    name = fields[0]
                    
                    # Preço informado (provavelmente BRL) -> converte para CAD pela taxa 0.25
                    price_cad = 100.0
                    try:
                        price_str = ''.join(c for c in fields[1] if c.isdigit() or c == '.')
                        if price_str:
                            price_brl = float(price_str)
                            price_cad = price_brl * 0.25
                    except Exception as e:
                        raise ValueError(f"Invalid price for {name}: {str(e)}")
                    
                    # Nota do hotel
                    rating = 4.0
                    try:
                        rating_str = fields[2].replace(',', '.')
                        rating_str = ''.join(c for c in rating_str if c.isdigit() or c == '.')
                        if rating_str:
                            rating = float(rating_str)
                    except Exception as e:
                        raise ValueError(f"Invalid rating for {name}: {str(e)}")
                    
                    # Cria instância Hotel
                    hotel = Hotel(
                        name=name,
                        price=price_cad,
                        rating=rating
                    )
                    # Adiciona à lista
                    hotels.append(hotel)
                except Exception as e:
                    # Loga erro na linha
                    print(f"Error processing hotel: {str(e)} in line: {line}")
        
        # Log de sucesso
        print(f"Loaded {len(hotels)} hotels.")
        return hotels
    
    @staticmethod
    def load_transport_matrices(base_path: str) -> bool:
        # Carrega todas as matrizes a partir do diretório base
        try:
            # Reseta todas as estruturas em memória
            for i in range(4):
                TransportMatrices.attraction_to_attraction_times[i] = []
                TransportMatrices.hotel_to_attraction_times[i] = []
                TransportMatrices.attraction_to_hotel_times[i] = []
            
            TransportMatrices.attraction_indices = {}
            TransportMatrices.hotel_indices = {}
            TransportMatrices.attraction_names = []
            TransportMatrices.hotel_names = []
            
            # Define o caminho da pasta com CSVs de tempo de deslocamento
            travel_times_path = os.path.join(base_path, "travel-times")
            if not os.path.exists(travel_times_path):
                raise RuntimeError(f"Travel times directory not found: {travel_times_path}")
            
            # Arquivos de matriz atração->atração para cada modo
            attraction_matrix_files = [
                os.path.join(travel_times_path, "attractions_matrix_WALK.csv"),
                os.path.join(travel_times_path, "attractions_matrix_SUBWAY_WALK.csv"),
                os.path.join(travel_times_path, "attractions_matrix_BUS_WALK.csv"),
                os.path.join(travel_times_path, "attractions_matrix_CAR_PICKUP.csv")
            ]
            
            # Arquivos hotel->atração (ida) por modo
            hotels_to_attractions_files = [
                os.path.join(travel_times_path, "hotels_to_attractions_WALK_GOING.csv"),
                os.path.join(travel_times_path, "hotels_to_attractions_SUBWAY_WALK_GOING.csv"),
                os.path.join(travel_times_path, "hotels_to_attractions_BUS_WALK_GOING.csv"),
                os.path.join(travel_times_path, "hotels_to_attractions_CAR_PICKUP_GOING.csv")
            ]
            
            # Arquivos atração->hotel (volta) por modo
            attractions_to_hotels_files = [
                os.path.join(travel_times_path, "hotels_to_attractions_WALK_RETURNING.csv"),
                os.path.join(travel_times_path, "hotels_to_attractions_SUBWAY_WALK_RETURNING.csv"),
                os.path.join(travel_times_path, "hotels_to_attractions_BUS_WALK_RETURNING.csv"),
                os.path.join(travel_times_path, "hotels_to_attractions_CAR_PICKUP_RETURNING.csv")
            ]
            
            # Lê arquivos de atração->atração
            for i, file_path in enumerate(attraction_matrix_files):
                if not os.path.exists(file_path):
                    print(f"Warning: Attraction matrix file not found: {file_path}")
                else:
                    # parse_matrix_file preenche a matriz e, na primeira, extrai nomes
                    _ = Parser.parse_matrix_file(
                        file_path,
                        TransportMatrices.attraction_to_attraction_times[i],
                        TransportMatrices.attraction_names,
                        is_hotel_rows=False,
                        is_hotel_cols=False,
                        extract_names=(i == 0)
                    )
            
            # Lê arquivos de hotel->atração (ida)
            for i, file_path in enumerate(hotels_to_attractions_files):
                if not os.path.exists(file_path):
                    print(f"Warning: Hotel-to-attraction matrix file not found: {file_path}")
                else:
                    _ = Parser.parse_matrix_file(
                        file_path,
                        TransportMatrices.hotel_to_attraction_times[i],
                        TransportMatrices.hotel_names,
                        is_hotel_rows=True,
                        is_hotel_cols=False,
                        extract_names=(i == 0)
                    )
            
            # Lê arquivos de atração->hotel (volta)
            for i, file_path in enumerate(attractions_to_hotels_files):
                if not os.path.exists(file_path):
                    print(f"Warning: Attraction-to-hotel matrix file not found: {file_path}")
                else:
                    _ = Parser.parse_matrix_file(
                        file_path,
                        TransportMatrices.attraction_to_hotel_times[i],
                        [],
                        is_hotel_rows=True,
                        is_hotel_cols=False,
                        extract_names=False
                    )
            
            # Marca como carregado e cria índices/mapeamentos
            TransportMatrices.matrices_loaded = True
            create_name_mappings()
            
            # Validação simples: verifica se ao menos a primeira matriz de cada tipo foi preenchida
            if (not TransportMatrices.attraction_to_attraction_times[0] or
                not TransportMatrices.hotel_to_attraction_times[0] or
                not TransportMatrices.attraction_to_hotel_times[0]):
                print("Error: One or more matrix files are empty")
                return False
            
            # Log de sucesso
            print(
                f"Loaded {len(TransportMatrices.attraction_names)} attractions and "
                f"{len(TransportMatrices.hotel_names)} hotels with travel matrices."
            )
            
            return True
        except Exception as e:
            # Loga erro genérico de carregamento
            print(f"Error loading matrices: {str(e)}")
            return False
    
    @staticmethod
    def parse_matrix_file(
        filename: str,
        matrix: List[List[float]],
        names: List[str],
        is_hotel_rows: bool,
        is_hotel_cols: bool,
        extract_names: bool
    ) -> bool:
        # Faz o parsing manual de um CSV de matriz, respeitando campos entre aspas
        try:
            # Abre arquivo para leitura
            with open(filename, 'r', encoding='utf-8') as file:
                # Lê cabeçalho e remove quebra de linha
                header = file.readline().strip()
                
                # Parser de cabeçalho com suporte a aspas
                header_parts = []
                current_field = ""
                in_quotes = False
                
                for char in header:
                    if char == '"':
                        in_quotes = not in_quotes
                    elif char == ',' and not in_quotes:
                        header_parts.append(current_field)
                        current_field = ""
                    else:
                        current_field += char
                
                # Adiciona último campo do cabeçalho
                header_parts.append(current_field)
                
                # Trata BOM (\ufeff) se presente no primeiro campo
                if header_parts and len(header_parts[0]) >= 3:
                    if header_parts[0].startswith('\ufeff'):
                        header_parts[0] = header_parts[0][1:]
                
                # Extrai nomes das colunas quando solicitado
                if extract_names and is_hotel_cols:
                    # Se a primeira coluna for vazia (título da diagonal), ignora
                    if header_parts and not header_parts[0].strip():
                        header_parts = header_parts[1:]
                    
                    for name in header_parts:
                        if name.strip() and name.strip() not in names:
                            names.append(name.strip())
                elif extract_names and not is_hotel_rows:
                    # Mesma lógica para matrizes que não têm hotel na linha
                    if header_parts and not header_parts[0].strip():
                        header_parts = header_parts[1:]
                    
                    for name in header_parts:
                        if name.strip() and name.strip() not in names:
                            names.append(name.strip())
                
                # Limpa a matriz e começa a ler as linhas
                matrix.clear()
                for line in file:
                    # Pula linhas vazias
                    if not line.strip():
                        continue
                    
                    # Parser linha com aspas
                    parts = []
                    current_field = ""
                    in_quotes = False
                    
                    for char in line:
                        if char == '"':
                            in_quotes = not in_quotes
                        elif char == ',' and not in_quotes:
                            parts.append(current_field)
                            current_field = ""
                        else:
                            current_field += char
                    
                    # Anexa último campo
                    parts.append(current_field)
                    
                    # Validação mínima
                    if len(parts) <= 1:
                        print(f"Warning: Invalid line in matrix file: {line}")
                        continue
                    
                    # Se for para extrair nomes nas linhas (hotéis), captura o primeiro campo
                    if extract_names and is_hotel_rows and parts[0].strip():
                        if parts[0].strip() not in names:
                            names.append(parts[0].strip())
                    
                    # Converte valores numéricos (N -> -1.0)
                    row = []
                    for i in range(1, len(parts)):
                        value_str = parts[i].strip()
                        
                        if value_str == "N" or not value_str:
                            row.append(-1.0)
                        else:
                            # Garante que é numérico simples
                            is_numeric = all(c.isdigit() or c in ".-" for c in value_str)
                            
                            if not is_numeric:
                                print(
                                    f"Warning: Non-numeric value '{value_str}' in matrix file {filename}. Using -1.0 instead."
                                )
                                row.append(-1.0)
                            else:
                                try:
                                    row.append(float(value_str.replace(',', '.')))
                                except Exception as e:
                                    print(
                                        f"Warning: Error parsing value '{value_str}' in matrix file {filename}: {str(e)}. Using -1.0 instead."
                                    )
                                    row.append(-1.0)
                    
                    # Adiciona linha convertida à matriz
                    matrix.append(row)
                
                # Retorna True se algo foi carregado
                return len(matrix) > 0
        except Exception as e:
            # Loga erro de parsing
            print(f"Error parsing matrix file {filename}: {str(e)}")
            return False
    
    @staticmethod
    def _parse_opening_hours(hours_str: str) -> Tuple[int, int]:
        # Converte string de horário "HH:MM-HH:MM" em minutos desde 00:00; trata casos especiais
        if not hours_str or hours_str in ["Fechado", "Closed"]:
            return -1, -1
        
        # Casos 24h
        if hours_str in ["00:00-23:59", "0:00-23:59", "24/7"]:
            return 0, 23 * 60 + 59
        
        try:
            # Encontra separador de faixa (vários tipos de travessão)
            dash_pos = hours_str.find('-')
            if dash_pos == -1:
                dash_pos = hours_str.find("–")
            if dash_pos == -1:
                dash_pos = hours_str.find("—")
            
            # Se não houver separador, formato inválido
            if dash_pos == -1:
                raise ValueError(f"Invalid time format: {hours_str}")
            
            # Separa partes de abertura/fechamento
            open_part = hours_str[:dash_pos].strip()
            close_part = hours_str[dash_pos+1:].strip()
            
            # Valida formato de abertura
            colon_pos = open_part.find(':')
            if colon_pos == -1:
                raise ValueError(f"Invalid opening time format: {open_part}")
            
            # Converte abertura
            hours = int(open_part[:colon_pos])
            minutes = int(open_part[colon_pos+1:].split()[0])
            opening_time = hours * 60 + minutes
            
            # Trata AM/PM se existir
            if "PM" in open_part.upper() and hours < 12:
                opening_time += 12 * 60
            elif "AM" in open_part.upper() and hours == 12:
                opening_time = 0
            
            # Converte fechamento; 00:00/24:00 tratadas como 23:59
            if close_part in ["0:00", "00:00", "24:00"]:
                closing_time = 23 * 60 + 59
            else:
                colon_pos = close_part.find(':')
                if colon_pos == -1:
                    raise ValueError(f"Invalid closing time format: {close_part}")
                
                hours = int(close_part[:colon_pos])
                minutes = int(close_part[colon_pos+1:].split()[0])
                closing_time = hours * 60 + minutes
                
                if "PM" in close_part.upper() and hours < 12:
                    closing_time += 12 * 60
                elif "AM" in close_part.upper() and hours == 12:
                    closing_time = 0
            
            # Ajuste: se fechar 00:00, usa 23:59 para evitar zero
            if closing_time == 0:
                closing_time = 23 * 60 + 59
            
            # Sanidade: abertura deve ser antes de fechamento (exceto 24h)
            if opening_time >= closing_time and not (opening_time == 0 and closing_time == 23 * 60 + 59):
                raise ValueError(
                    f"Opening time ({opening_time}) must be before closing time ({closing_time})"
                )
            
            # Retorna tupla (abertura, fechamento) em minutos
            return opening_time, closing_time
        except Exception as e:
            # Propaga erro com contexto
            raise ValueError(f"Error parsing hours '{hours_str}': {str(e)}")
