"""
Utility functions for data loading and transport calculations.
"""

import csv
import re
import os
from typing import Dict, List, Tuple, Set, Optional, Any
import pandas as pd
from models import Hotel, Attraction, TransportMode
from functools import lru_cache

class Config:
    DAILY_TIME_LIMIT = 12 * 60
    WALK_TIME_PREFERENCE = 20.0
    CAR_COST_PER_MINUTE = 1.0
    TOLERANCE = 0.05

class TransportMatrices:
    attraction_to_attraction_times = [[] for _ in range(4)]
    
    hotel_to_attraction_times = [[] for _ in range(4)]
    
    attraction_to_hotel_times = [[] for _ in range(4)]
    
    attraction_indices: Dict[str, int] = {}
    hotel_indices: Dict[str, int] = {}
    
    attraction_names: List[str] = []
    hotel_names: List[str] = []
    
    attraction_name_set: Set[str] = set()
    hotel_name_set: Set[str] = set()
    
    matrices_loaded = False

@lru_cache(maxsize=1000)
def normalize_string(s: str) -> str:
    if not s:
        return ""
    
    result = s.lower()
    
    result = re.sub(r'[^\w\s]', ' ', result)
    
    result = re.sub(r'\s+', ' ', result)
    
    result = result.strip()
    
    return result

def is_hotel(name: str) -> bool:
    if name in TransportMatrices.hotel_name_set:
        return True
    
    normalized = normalize_string(name)
    for hotel_name in TransportMatrices.hotel_names:
        if normalized == normalize_string(hotel_name):
            return True
    
    for hotel_name in TransportMatrices.hotel_names:
        norm_hotel = normalize_string(hotel_name)
        if norm_hotel in normalized or normalized in norm_hotel:
            return True
    
    if name in TransportMatrices.attraction_name_set:
        return False
    
    for attr_name in TransportMatrices.attraction_names:
        if normalized == normalize_string(attr_name):
            return False
    
    hotel_indicators = ["hotel", "hôtel", "auberge", "inn", "suites", "hostel", 
                      "marriott", "hilton", "sheraton", "westin", "hyatt", "fairmont"]
    
    words = normalized.split()
    for word in words:
        if word in hotel_indicators:
            return True
    
    return False

def create_entity_sets():
    TransportMatrices.hotel_name_set = set(TransportMatrices.hotel_names)
    TransportMatrices.attraction_name_set = set(TransportMatrices.attraction_names)
    
    print(f"Created entity sets with {len(TransportMatrices.hotel_name_set)} hotels and "
          f"{len(TransportMatrices.attraction_name_set)} attractions")

def create_name_mappings():
    if not TransportMatrices.matrices_loaded:
        print("Error: transport matrices not loaded before creating mappings.")
        return
    
    TransportMatrices.attraction_indices.clear()
    TransportMatrices.hotel_indices.clear()
    
    for i, name in enumerate(TransportMatrices.attraction_names):
        normalized = normalize_string(name)
        TransportMatrices.attraction_indices[normalized] = i
        no_spaces = normalized.replace(" ", "")
        TransportMatrices.attraction_indices[no_spaces] = i
    
    for i, name in enumerate(TransportMatrices.hotel_names):
        normalized = normalize_string(name)
        TransportMatrices.hotel_indices[normalized] = i
        no_spaces = normalized.replace(" ", "")
        TransportMatrices.hotel_indices[no_spaces] = i
        
        words = normalized.split()
        if len(words) > 1 and words[0] in ["hotel", "hôtel", "auberge"]:
            first_word_removed = ' '.join(words[1:])
            TransportMatrices.hotel_indices[first_word_removed] = i
    
    create_entity_sets()
    
    print(f"Name mappings created for {len(TransportMatrices.attraction_names)} attractions and "
          f"{len(TransportMatrices.hotel_names)} hotels.")

def find_matrix_name(original_name: str, is_hotel: bool = False) -> str:
    if "place d'armes" in original_name.lower() or "place darmes" in original_name.lower():
        return "Place d'Armes"
        
    normalized_name = normalize_string(original_name)
    
    if is_hotel:
        for hotel_name in TransportMatrices.hotel_names:
            if normalized_name == normalize_string(hotel_name):
                return hotel_name
    else:
        for attr_name in TransportMatrices.attraction_names:
            if normalized_name == normalize_string(attr_name):
                return attr_name
    
    return original_name

def find_attraction_index(name: str) -> int:
    if is_hotel(name):
        return -1
    
    normalized = normalize_string(name)
    
    if normalized in TransportMatrices.attraction_indices:
        return TransportMatrices.attraction_indices[normalized]
    
    no_spaces = normalized.replace(" ", "")
    if no_spaces in TransportMatrices.attraction_indices:
        return TransportMatrices.attraction_indices[no_spaces]
    
    for attr_name in TransportMatrices.attraction_names:
        norm_attr = normalize_string(attr_name)
        if normalized in norm_attr or norm_attr in normalized:
            return TransportMatrices.attraction_indices[norm_attr]
    
    return -1

def find_hotel_index(name: str) -> int:
    if not is_hotel(name):
        return -1
    
    normalized = normalize_string(name)
    
    if normalized in TransportMatrices.hotel_indices:
        return TransportMatrices.hotel_indices[normalized]
    
    no_spaces = normalized.replace(" ", "")
    if no_spaces in TransportMatrices.hotel_indices:
        return TransportMatrices.hotel_indices[no_spaces]
    
    words = normalized.split()
    if len(words) > 1 and words[0] in ["hotel", "hôtel", "auberge"]:
        first_word_removed = ' '.join(words[1:])
        if first_word_removed in TransportMatrices.hotel_indices:
            return TransportMatrices.hotel_indices[first_word_removed]
    
    for hotel_name in TransportMatrices.hotel_names:
        norm_hotel = normalize_string(hotel_name)
        if normalized in norm_hotel or norm_hotel in normalized:
            return TransportMatrices.hotel_indices[norm_hotel]
    
    return -1

class Transport:
    
    _travel_time_cache = {}
    
    _mode_compatibility_cache = {}
    
    @staticmethod
    def get_distance(from_name: str, to_name: str, mode: TransportMode) -> float:
        return Transport.get_travel_time(from_name, to_name, mode) * 20
    
    @staticmethod
    def get_travel_time(from_name: str, to_name: str, mode: TransportMode) -> float:
        if not TransportMatrices.matrices_loaded:
            raise RuntimeError("Transport matrices not loaded. Call load_transport_matrices first.")
        
        cache_key = (from_name, to_name, mode.value)
        if cache_key in Transport._travel_time_cache:
            return Transport._travel_time_cache[cache_key]
        
        if "Place d'Armes" in from_name or "Place d'Armes" in to_name:
            Transport._travel_time_cache[cache_key] = 15.0
            return 15.0
            
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
        
        if from_idx == -1:
            return -1.0
        
        if to_idx == -1:
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
        
        if hotel_idx == -1:
            return -1.0
        
        if attr_idx == -1:
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
        
        if attr_idx == -1:
            return -1.0
        
        if hotel_idx == -1:
            return -1.0
        
        mode_idx = mode.value
        matrix = TransportMatrices.attraction_to_hotel_times[mode_idx]
        
        
        if hotel_idx >= len(matrix) or attr_idx >= len(matrix[hotel_idx]):
            return -1.0
        
        time = matrix[hotel_idx][attr_idx]
        
        if time < 0:
            return -1.0
        
        return time
    
    @staticmethod
    def get_travel_cost(from_name: str, to_name: str, mode: TransportMode) -> float:
        if mode == TransportMode.CAR:
            return Transport.get_travel_time(from_name, to_name, mode) * Config.CAR_COST_PER_MINUTE
        else:
            return 0.0
    
    @staticmethod
    def get_valid_transport_modes(from_name: str, to_name: str) -> List[TransportMode]:
        cache_key = (from_name, to_name)
        if cache_key in Transport._mode_compatibility_cache:
            return Transport._mode_compatibility_cache[cache_key]
        
        valid_modes = []
        for mode in [TransportMode.CAR, TransportMode.BUS_WALK, TransportMode.SUBWAY_WALK, TransportMode.WALK]:
            travel_time = Transport.get_travel_time(from_name, to_name, mode)
            if travel_time >= 0:
                valid_modes.append(mode)
        
        Transport._mode_compatibility_cache[cache_key] = valid_modes
        return valid_modes
    
    @staticmethod
    def determine_preferred_mode(from_name: str, to_name: str) -> TransportMode:
        valid_modes = Transport.get_valid_transport_modes(from_name, to_name)
        
        if not valid_modes:
            return TransportMode.CAR
        
        if TransportMode.WALK in valid_modes:
            walk_time = Transport.get_travel_time(from_name, to_name, TransportMode.WALK)
            if walk_time <= Config.WALK_TIME_PREFERENCE:
                return TransportMode.WALK
        
        if TransportMode.SUBWAY_WALK in valid_modes:
            return TransportMode.SUBWAY_WALK
        
        if TransportMode.BUS_WALK in valid_modes:
            return TransportMode.BUS_WALK
        
        return valid_modes[0]
    
    @staticmethod
    def format_time(minutes: float) -> str:
        total_minutes = int(minutes)
        hours = total_minutes // 60
        mins = total_minutes % 60
        return f"{hours:02d}:{mins:02d}"

class Parser:
    
    @staticmethod
    def load_attractions(filename: str) -> List[Attraction]:
        attractions = []
        
        with open(filename, 'r', encoding='utf-8') as file:
            next(file)
            
            for line in file:
                if not line.strip() or line.strip().startswith('#'):
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
                    try:
                        name = fields[1]
                        neighborhood = fields[3]
                        
                        rating = 4.0
                        try:
                            rating_str = fields[5].replace(',', '.')
                            rating = float(rating_str)
                        except Exception as e:
                            raise ValueError(f"Invalid rating for {name}: {str(e)}")
                        
                        cost = 0.0
                        try:
                            cost_str = fields[6].replace(',', '.')
                            cost = float(cost_str)
                        except Exception as e:
                            raise ValueError(f"Invalid cost for {name}: {str(e)}")
                        
                        saturday_opening_time, saturday_closing_time = Parser._parse_opening_hours(fields[7])
                        
                        sunday_opening_time, sunday_closing_time = Parser._parse_opening_hours(fields[8])
                        
                        visit_time = 60
                        try:
                            visit_time = int(fields[9])
                        except Exception as e:
                            raise ValueError(f"Invalid visit time for {name}: {str(e)}")
                        
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
                    except Exception as e:
                        print(f"Error processing attraction: {str(e)} in line: {line}")
                else:
                    print(f"Warning: CSV line has too few fields: {line}")
        
        if not attractions:
            raise RuntimeError(f"No valid attractions loaded from: {filename}")
        
        print(f"Loaded {len(attractions)} attractions.")
        return attractions
    
    @staticmethod
    def load_hotels(filename: str) -> List[Hotel]:
        hotels = []
        
        with open(filename, 'r', encoding='utf-8') as file:
            next(file)
            
            for line in file:
                if not line.strip() or line.strip().startswith('#'):
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
                
                if len(fields) < 3:
                    print(f"Warning: CSV line has too few fields: {line}")
                    continue
                
                try:
                    name = fields[0]
                    
                    price_cad = 100.0
                    try:
                        price_str = ''.join(c for c in fields[1] if c.isdigit() or c == '.')
                        if price_str:
                            price_brl = float(price_str)
                            price_cad = price_brl * 0.25
                    except Exception as e:
                        raise ValueError(f"Invalid price for {name}: {str(e)}")
                    
                    rating = 4.0
                    try:
                        rating_str = fields[2].replace(',', '.')
                        rating_str = ''.join(c for c in rating_str if c.isdigit() or c == '.')
                        if rating_str:
                            rating = float(rating_str)
                    except Exception as e:
                        raise ValueError(f"Invalid rating for {name}: {str(e)}")
                    
                    hotel = Hotel(
                        name=name,
                        price=price_cad,
                        rating=rating
                    )
                    hotels.append(hotel)
                except Exception as e:
                    print(f"Error processing hotel: {str(e)} in line: {line}")
        
        print(f"Loaded {len(hotels)} hotels.")
        return hotels
    
    @staticmethod
    def load_transport_matrices(base_path: str) -> bool:
        try:
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
                raise RuntimeError(f"Travel times directory not found: {travel_times_path}")
            
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
                if not os.path.exists(file_path):
                    print(f"Warning: Attraction matrix file not found: {file_path}")
                else:
                    result = Parser.parse_matrix_file(
                        file_path,
                        TransportMatrices.attraction_to_attraction_times[i],
                        TransportMatrices.attraction_names,
                        is_hotel_rows=False,
                        is_hotel_cols=False,
                        extract_names=(i == 0)
                    )
            
            for i, file_path in enumerate(hotels_to_attractions_files):
                if not os.path.exists(file_path):
                    print(f"Warning: Hotel-to-attraction matrix file not found: {file_path}")
                else:
                    result = Parser.parse_matrix_file(
                        file_path,
                        TransportMatrices.hotel_to_attraction_times[i],
                        TransportMatrices.hotel_names,
                        is_hotel_rows=True,
                        is_hotel_cols=False,
                        extract_names=(i == 0)
                    )
            
            for i, file_path in enumerate(attractions_to_hotels_files):
                if not os.path.exists(file_path):
                    print(f"Warning: Attraction-to-hotel matrix file not found: {file_path}")
                else:
                    result = Parser.parse_matrix_file(
                        file_path,
                        TransportMatrices.attraction_to_hotel_times[i],
                        [],
                        is_hotel_rows=True,
                        is_hotel_cols=False,
                        extract_names=False
                    )
            
            TransportMatrices.matrices_loaded = True
            create_name_mappings()
            
            if (not TransportMatrices.attraction_to_attraction_times[0] or
                not TransportMatrices.hotel_to_attraction_times[0] or
                not TransportMatrices.attraction_to_hotel_times[0]):
                print("Error: One or more matrix files are empty")
                return False
            
            print(f"Loaded {len(TransportMatrices.attraction_names)} attractions and "
                  f"{len(TransportMatrices.hotel_names)} hotels with travel matrices.")
            
            return True
        except Exception as e:
            print(f"Error loading matrices: {str(e)}")
            return False
    
    @staticmethod
    def parse_matrix_file(filename: str, matrix: List[List[float]], names: List[str],
                          is_hotel_rows: bool, is_hotel_cols: bool, extract_names: bool) -> bool:
        try:
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
                
                if header_parts and len(header_parts[0]) >= 3:
                    if header_parts[0].startswith('\ufeff'):
                        header_parts[0] = header_parts[0][1:]
                
                if extract_names and is_hotel_cols:
                    if header_parts and not header_parts[0].strip():
                        header_parts = header_parts[1:]
                    
                    for name in header_parts:
                        if name.strip() and name.strip() not in names:
                            names.append(name.strip())
                elif extract_names and not is_hotel_rows:
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
                        print(f"Warning: Invalid line in matrix file: {line}")
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
                            is_numeric = all(c.isdigit() or c in ".-" for c in value_str)
                            
                            if not is_numeric:
                                print(f"Warning: Non-numeric value '{value_str}' in matrix file {filename}. Using -1.0 instead.")
                                row.append(-1.0)
                            else:
                                try:
                                    row.append(float(value_str.replace(',', '.')))
                                except Exception as e:
                                    print(f"Warning: Error parsing value '{value_str}' in matrix file {filename}: {str(e)}. Using -1.0 instead.")
                                    row.append(-1.0)
                    
                    matrix.append(row)
                
                return len(matrix) > 0
        except Exception as e:
            print(f"Error parsing matrix file {filename}: {str(e)}")
            return False
    
    @staticmethod
    def _parse_opening_hours(hours_str: str) -> Tuple[int, int]:
        if not hours_str or hours_str in ["Fechado", "Closed"]:
            return -1, -1
        
        if hours_str in ["00:00-23:59", "0:00-23:59", "24/7"]:
            return 0, 23 * 60 + 59
        
        try:
            dash_pos = hours_str.find('-')
            if dash_pos == -1:
                dash_pos = hours_str.find("–")
            if dash_pos == -1:
                dash_pos = hours_str.find("—")
            
            if dash_pos == -1:
                raise ValueError(f"Invalid time format: {hours_str}")
            
            open_part = hours_str[:dash_pos].strip()
            close_part = hours_str[dash_pos+1:].strip()
            
            colon_pos = open_part.find(':')
            if colon_pos == -1:
                raise ValueError(f"Invalid opening time format: {open_part}")
            
            hours = int(open_part[:colon_pos])
            minutes = int(open_part[colon_pos+1:].split()[0])
            opening_time = hours * 60 + minutes
            
            if "PM" in open_part.upper() and hours < 12:
                opening_time += 12 * 60
            elif "AM" in open_part.upper() and hours == 12:
                opening_time = 0
            
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
            
            if closing_time == 0:
                closing_time = 23 * 60 + 59
            
            if opening_time >= closing_time and not (opening_time == 0 and closing_time == 23 * 60 + 59):
                raise ValueError(f"Opening time ({opening_time}) must be before closing time ({closing_time})")
            
            return opening_time, closing_time
        except Exception as e:
            raise ValueError(f"Error parsing hours '{hours_str}': {str(e)}")