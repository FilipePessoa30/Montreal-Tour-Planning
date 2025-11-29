import os
import re
from typing import Dict, List, Tuple
from models import Hotel, Attraction, TransportMode

class Config:
    DAILY_TIME_LIMIT = 12 * 60
    WALK_TIME_PREFERENCE = 20.0
    CAR_COST_PER_MINUTE = 1.0

class TransportMatrices:
    attraction_to_attraction_times = [[] for _ in range(4)]
    hotel_to_attraction_times = [[] for _ in range(4)]
    attraction_to_hotel_times = [[] for _ in range(4)]
    attraction_indices: Dict[str, int] = {}
    hotel_indices: Dict[str, int] = {}
    attraction_names: List[str] = []
    hotel_names: List[str] = []
    matrices_loaded = False

def normalize_string(s: str) -> str:
    if not s:
        return ""
    result = s.lower()
    result = re.sub(r'[^\w\s]', ' ', result)
    result = re.sub(r'\s+', ' ', result)
    result = result.strip()
    return result

def is_hotel(name: str) -> bool:
    normalized = normalize_string(name)
    for hotel_name in TransportMatrices.hotel_names:
        if normalized == normalize_string(hotel_name):
            return True
    for attr_name in TransportMatrices.attraction_names:
        if normalized == normalize_string(attr_name):
            return False
    return False

def find_attraction_index(name: str) -> int:
    if is_hotel(name):
        return -1
    normalized = normalize_string(name)
    if normalized in TransportMatrices.attraction_indices:
        return TransportMatrices.attraction_indices[normalized]
    for attr_name in TransportMatrices.attraction_names:
        norm_attr = normalize_string(attr_name)
        if normalized in norm_attr or norm_attr in normalized:
            if norm_attr in TransportMatrices.attraction_indices:
                return TransportMatrices.attraction_indices[norm_attr]
    return -1

def find_hotel_index(name: str) -> int:
    normalized = normalize_string(name)
    if normalized in TransportMatrices.hotel_indices:
        return TransportMatrices.hotel_indices[normalized]
    for hotel_name in TransportMatrices.hotel_names:
        norm_hotel = normalize_string(hotel_name)
        if normalized in norm_hotel or norm_hotel in normalized:
            if norm_hotel in TransportMatrices.hotel_indices:
                return TransportMatrices.hotel_indices[norm_hotel]
    return -1

class Transport:
    _travel_time_cache = {}

    @staticmethod
    def get_travel_time(from_name: str, to_name: str, mode: TransportMode) -> float:
        if not TransportMatrices.matrices_loaded:
            return -1.0
        cache_key = (from_name, to_name, mode.value)
        if cache_key in Transport._travel_time_cache:
            return Transport._travel_time_cache[cache_key]
        from_is_hotel = is_hotel(from_name)
        to_is_hotel = is_hotel(to_name)
        if from_is_hotel and to_is_hotel:
            result = -1.0
        elif from_is_hotel and not to_is_hotel:
            result = Transport.get_hotel_to_attraction_time(from_name, to_name, mode)
        elif not from_is_hotel and to_is_hotel:
            result = Transport.get_attraction_to_hotel_time(from_name, to_name, mode)
        else:
            result = Transport.get_attraction_to_attraction_time(from_name, to_name, mode)
        Transport._travel_time_cache[cache_key] = result
        return result

    @staticmethod
    def get_attraction_to_attraction_time(from_name: str, to_name: str, mode: TransportMode) -> float:
        from_idx = find_attraction_index(from_name)
        to_idx = find_attraction_index(to_name)
        if from_idx == -1 or to_idx == -1:
            return -1.0
        mode_idx = mode.value
        matrix = TransportMatrices.attraction_to_attraction_times[mode_idx]
        if from_idx >= len(matrix) or to_idx >= len(matrix[from_idx]):
            return -1.0
        time = matrix[from_idx][to_idx]
        if time < 0:
            return -1.0
        return time

    @staticmethod
    def get_hotel_to_attraction_time(from_name: str, to_name: str, mode: TransportMode) -> float:
        hotel_idx = find_hotel_index(from_name)
        attr_idx = find_attraction_index(to_name)
        if hotel_idx == -1 or attr_idx == -1:
            return -1.0
        mode_idx = mode.value
        matrix = TransportMatrices.hotel_to_attraction_times[mode_idx]
        if hotel_idx >= len(matrix) or attr_idx >= len(matrix[hotel_idx]):
            return -1.0
        time = matrix[hotel_idx][attr_idx]
        if time < 0:
            return -1.0
        return time

    @staticmethod
    def get_attraction_to_hotel_time(from_name: str, to_name: str, mode: TransportMode) -> float:
        attr_idx = find_attraction_index(from_name)
        hotel_idx = find_hotel_index(to_name)
        if attr_idx == -1 or hotel_idx == -1:
            return -1.0
        mode_idx = mode.value
        matrix = TransportMatrices.attraction_to_hotel_times[mode_idx]
        if hotel_idx >= len(matrix) or attr_idx >= len(matrix[hotel_idx]):
            return -1.0
        time = matrix[hotel_idx][attr_idx]
        if time < 0:
            return -1.0
        return time

class Parser:
    @staticmethod
    def load_attractions(filename: str) -> List[Attraction]:
        attractions = []
        with open(filename, 'r', encoding='utf-8') as file:
            next(file)
            for line in file:
                if not line.strip():
                    continue
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
                if current_field:
                    fields.append(current_field)
                fields = [field.strip() for field in fields]
                if len(fields) >= 10:
                    name = fields[1]
                    neighborhood = fields[3]
                    rating = float(fields[5].replace(',', '.'))
                    cost = float(fields[6].replace(',', '.'))
                    saturday_opening_time, saturday_closing_time = Parser._parse_opening_hours(fields[7])
                    sunday_opening_time, sunday_closing_time = Parser._parse_opening_hours(fields[8])
                    visit_time = int(fields[9])
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
                    attractions.append(attraction)
        return attractions

    @staticmethod
    def load_hotels(filename: str) -> List[Hotel]:
        hotels = []
        with open(filename, 'r', encoding='utf-8') as file:
            next(file)
            for line in file:
                if not line.strip():
                    continue
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
                fields.append(current_field)
                for i in range(len(fields)):
                    field = fields[i]
                    if len(field) >= 2 and field[0] == '"' and field[-1] == '"':
                        field = field[1:-1]
                    fields[i] = field.strip()
                if len(fields) >= 3:
                    name = fields[0]
                    price_str = ''.join(c for c in fields[1] if c.isdigit() or c == '.')
                    price_cad = float(price_str) * 0.25 if price_str else 100.0
                    rating_str = fields[2].replace(',', '.')
                    rating_str = ''.join(c for c in rating_str if c.isdigit() or c == '.')
                    rating = float(rating_str) if rating_str else 4.0
                    hotel = Hotel(name=name, price=price_cad, rating=rating)
                    hotels.append(hotel)
        return hotels

    @staticmethod
    def load_transport_matrices(base_path: str) -> bool:
        for i in range(4):
            TransportMatrices.attraction_to_attraction_times[i] = []
            TransportMatrices.hotel_to_attraction_times[i] = []
            TransportMatrices.attraction_to_hotel_times[i] = []
        TransportMatrices.attraction_indices = {}
        TransportMatrices.hotel_indices = {}
        TransportMatrices.attraction_names = []
        TransportMatrices.hotel_names = []
        travel_times_path = os.path.join(base_path, "travel-times")
        if not os.path.exists(travel_times_path):
            return False
        attraction_matrix_files = [
            os.path.join(travel_times_path, "attractions_matrix_WALK.csv"),
            os.path.join(travel_times_path, "attractions_matrix_SUBWAY_WALK.csv"),
            os.path.join(travel_times_path, "attractions_matrix_BUS_WALK.csv"),
            os.path.join(travel_times_path, "attractions_matrix_CAR_PICKUP.csv")
        ]
        hotels_to_attractions_files = [
            os.path.join(travel_times_path, "hotels_to_attractions_WALK_GOING.csv"),
            os.path.join(travel_times_path, "hotels_to_attractions_SUBWAY_WALK_GOING.csv"),
            os.path.join(travel_times_path, "hotels_to_attractions_BUS_WALK_GOING.csv"),
            os.path.join(travel_times_path, "hotels_to_attractions_CAR_PICKUP_GOING.csv")
        ]
        attractions_to_hotels_files = [
            os.path.join(travel_times_path, "hotels_to_attractions_WALK_RETURNING.csv"),
            os.path.join(travel_times_path, "hotels_to_attractions_SUBWAY_WALK_RETURNING.csv"),
            os.path.join(travel_times_path, "hotels_to_attractions_BUS_WALK_RETURNING.csv"),
            os.path.join(travel_times_path, "hotels_to_attractions_CAR_PICKUP_RETURNING.csv")
        ]
        for i, file_path in enumerate(attraction_matrix_files):
            if os.path.exists(file_path):
                Parser.parse_matrix_file(
                    file_path,
                    TransportMatrices.attraction_to_attraction_times[i],
                    TransportMatrices.attraction_names,
                    is_hotel_rows=False,
                    extract_names=(i == 0)
                )
        for i, file_path in enumerate(hotels_to_attractions_files):
            if os.path.exists(file_path):
                Parser.parse_matrix_file(
                    file_path,
                    TransportMatrices.hotel_to_attraction_times[i],
                    TransportMatrices.hotel_names,
                    is_hotel_rows=True,
                    extract_names=(i == 0)
                )
        for i, file_path in enumerate(attractions_to_hotels_files):
            if os.path.exists(file_path):
                Parser.parse_matrix_file(
                    file_path,
                    TransportMatrices.attraction_to_hotel_times[i],
                    [],
                    is_hotel_rows=True,
                    extract_names=False
                )
        TransportMatrices.matrices_loaded = True
        for i, name in enumerate(TransportMatrices.attraction_names):
            normalized = normalize_string(name)
            TransportMatrices.attraction_indices[normalized] = i
        for i, name in enumerate(TransportMatrices.hotel_names):
            normalized = normalize_string(name)
            TransportMatrices.hotel_indices[normalized] = i
        return True

    @staticmethod
    def parse_matrix_file(filename: str, matrix: List[List[float]], names: List[str],
                          is_hotel_rows: bool, extract_names: bool) -> bool:
        with open(filename, 'r', encoding='utf-8') as file:
            header = file.readline().strip()
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
            header_parts.append(current_field)
            if header_parts and header_parts[0].startswith('\ufeff'):
                header_parts[0] = header_parts[0][1:]
            if extract_names and not is_hotel_rows:
                if header_parts and not header_parts[0].strip():
                    header_parts = header_parts[1:]
                for name in header_parts:
                    if name.strip() and name.strip() not in names:
                        names.append(name.strip())
            matrix.clear()
            for line in file:
                if not line.strip():
                    continue
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
                parts.append(current_field)
                if len(parts) <= 1:
                    continue
                if extract_names and is_hotel_rows and parts[0].strip():
                    if parts[0].strip() not in names:
                        names.append(parts[0].strip())
                row = []
                for i in range(1, len(parts)):
                    value_str = parts[i].strip()
                    if value_str == "N" or not value_str:
                        row.append(-1.0)
                    else:
                        try:
                            row.append(float(value_str.replace(',', '.')))
                        except:
                            row.append(-1.0)
                matrix.append(row)
            return len(matrix) > 0

    @staticmethod
    def _parse_opening_hours(hours_str: str) -> Tuple[int, int]:
        if not hours_str or hours_str in ["Fechado", "Closed"]:
            return -1, -1
        if hours_str in ["00:00-23:59", "0:00-23:59", "24/7"]:
            return 0, 23 * 60 + 59
        dash_pos = hours_str.find('-')
        if dash_pos == -1:
            dash_pos = hours_str.find("–")
        if dash_pos == -1:
            return -1, -1
        open_part = hours_str[:dash_pos].strip()
        close_part = hours_str[dash_pos + 1:].strip()
        colon_pos = open_part.find(':')
        if colon_pos == -1:
            return -1, -1
        hours = int(open_part[:colon_pos])
        minutes = int(open_part[colon_pos + 1:].split()[0])
        opening_time = hours * 60 + minutes
        if close_part in ["0:00", "00:00", "24:00"]:
            closing_time = 23 * 60 + 59
        else:
            colon_pos = close_part.find(':')
            if colon_pos == -1:
                return -1, -1
            hours = int(close_part[:colon_pos])
            minutes = int(close_part[colon_pos + 1:].split()[0])
            closing_time = hours * 60 + minutes
        if closing_time == 0:
            closing_time = 23 * 60 + 59
        return opening_time, closing_time
