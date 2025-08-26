
import os
import random
import time
from typing import List, Dict, Tuple, Set, Optional, Any
from models import Attraction, Hotel, DailyRoute, TransportMode, Solution
from utils import Parser, Transport, normalize_string
from functools import lru_cache
import copy

class MOVNSConstructor:
    
    def __init__(self, attractions_file: str, hotels_file: str, matrices_path: str):
        self.attractions = Parser.load_attractions(attractions_file)
        self.hotels = Parser.load_hotels(hotels_file)
        
        success = Parser.load_transport_matrices(matrices_path)
        if not success:
            raise RuntimeError("Failed to load transport matrices")
        
        self.attraction_by_name = {attr.name: attr for attr in self.attractions}
        self.hotel_by_name = {hotel.name: hotel for hotel in self.hotels}
        
        self.working_hotels = []
        
        print("Pre-calculating attraction availability...")
        
        self.saturday_open_attractions = []
        self.sunday_open_attractions = []
        
        for attr in self.attractions:
            if attr.is_open_on_day(True):
                self.saturday_open_attractions.append(attr)
            
            if attr.is_open_on_day(False):
                self.sunday_open_attractions.append(attr)
                
        print(f"Found {len(self.saturday_open_attractions)} attractions open on Saturday")
        print(f"Found {len(self.sunday_open_attractions)} attractions open on Sunday")
        
        self._mode_validation_cache = {}
        
        self._attraction_compatibility_matrix = {}
        self._hotel_attraction_compatibility = {}
        self._attraction_hotel_compatibility = {}
        
        print("Building compatibility matrices...")
        self._build_compatibility_matrices()
        
        self.validate_data_consistency()
    
    def _build_compatibility_matrices(self):
        for hotel in self.hotels:
            self._hotel_attraction_compatibility[hotel.name] = {}
            
            for attr in self.saturday_open_attractions:
                valid_modes = []
                for mode in [TransportMode.CAR, TransportMode.BUS_WALK, TransportMode.SUBWAY_WALK, TransportMode.WALK]:
                    travel_time = Transport.get_travel_time(hotel.name, attr.name, mode)
                    if travel_time >= 0:
                        arrival_time = 8 * 60 + travel_time
                        if arrival_time < attr.saturday_closing_time:
                            if arrival_time < attr.saturday_opening_time:
                                arrival_time = attr.saturday_opening_time
                            
                            if arrival_time + attr.visit_time <= attr.saturday_closing_time:
                                valid_modes.append(mode)
                
                if valid_modes:
                    self._hotel_attraction_compatibility[hotel.name][attr.name] = {
                        "saturday": valid_modes,
                        "modes": valid_modes
                    }
            
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
                    if attr.name not in self._hotel_attraction_compatibility[hotel.name]:
                        self._hotel_attraction_compatibility[hotel.name][attr.name] = {"modes": valid_modes}
                    
                    self._hotel_attraction_compatibility[hotel.name][attr.name]["sunday"] = valid_modes
        
        self._attraction_hotel_compatibility = {}
        
        for attr in self.attractions:
            if attr.name not in self._attraction_hotel_compatibility:
                self._attraction_hotel_compatibility[attr.name] = {}
            
            for hotel in self.hotels:
                valid_return_modes = []
                
                latest_departure_saturday = -1
                latest_departure_sunday = -1
                
                if attr.is_open_on_day(True):
                    latest_departure_saturday = min(attr.saturday_closing_time, 20 * 60)
                
                if attr.is_open_on_day(False):
                    latest_departure_sunday = min(attr.sunday_closing_time, 20 * 60)
                
                for mode in [TransportMode.CAR, TransportMode.BUS_WALK, TransportMode.SUBWAY_WALK, TransportMode.WALK]:
                    travel_time = Transport.get_travel_time(attr.name, hotel.name, mode)
                    
                    if travel_time >= 0:
                        if (latest_departure_saturday != -1 and 
                            latest_departure_saturday + travel_time <= 20 * 60) or \
                           (latest_departure_sunday != -1 and 
                            latest_departure_sunday + travel_time <= 20 * 60):
                            valid_return_modes.append(mode)
                
                if valid_return_modes:
                    self._attraction_hotel_compatibility[attr.name][hotel.name] = valid_return_modes
        
        for from_attr in self.attractions:
            self._attraction_compatibility_matrix[from_attr.name] = {}
            
            for to_attr in self.attractions:
                if from_attr.name != to_attr.name:
                    sat_valid_modes = []
                    if from_attr.is_open_on_day(True) and to_attr.is_open_on_day(True):
                        for mode in [TransportMode.CAR, TransportMode.BUS_WALK, TransportMode.SUBWAY_WALK, TransportMode.WALK]:
                            travel_time = Transport.get_travel_time(from_attr.name, to_attr.name, mode)
                            if travel_time >= 0:
                                earliest_departure = from_attr.saturday_opening_time + from_attr.visit_time
                                
                                latest_departure = from_attr.saturday_closing_time
                                
                                earliest_arrival = earliest_departure + travel_time
                                
                                if earliest_arrival < to_attr.saturday_closing_time:
                                    if earliest_arrival < to_attr.saturday_opening_time:
                                        earliest_arrival = to_attr.saturday_opening_time
                                    
                                    if earliest_arrival + to_attr.visit_time <= to_attr.saturday_closing_time:
                                        sat_valid_modes.append(mode)
                    
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
                    
                    if sat_valid_modes or sun_valid_modes:
                        self._attraction_compatibility_matrix[from_attr.name][to_attr.name] = {
                            "saturday": sat_valid_modes,
                            "sunday": sun_valid_modes
                        }
        
        hotel_attr_connections = sum(len(hotel_data) for hotel_data in self._hotel_attraction_compatibility.values())
        attr_attr_connections = sum(len(attr_data) for attr_data in self._attraction_compatibility_matrix.values())
        attr_hotel_connections = sum(len(attr_data) for attr_data in self._attraction_hotel_compatibility.values() if isinstance(attr_data, dict))
        
        print(f"Built compatibility matrices with:")
        print(f"  - {hotel_attr_connections} hotel-to-attraction connections")
        print(f"  - {attr_attr_connections} attraction-to-attraction connections")
        print(f"  - {attr_hotel_connections} attraction-to-hotel connections")
    
    def validate_data_consistency(self) -> bool:
        print("Validating data consistency...")
        
        print(f"Validating {len(self.attractions)} attractions...")
        attraction_problems = 0
        valid_attractions = []
        
        for attraction in self.attractions:
            valid_connection_count = 0
            
            sample_hotels = random.sample(self.hotels, min(10, len(self.hotels)))
            
            for hotel in sample_hotels:
                for mode in [TransportMode.CAR, TransportMode.BUS_WALK, TransportMode.SUBWAY_WALK, TransportMode.WALK]:
                    time_to = Transport.get_travel_time(hotel.name, attraction.name, mode)
                    time_from = Transport.get_travel_time(attraction.name, hotel.name, mode)
                    
                    if time_to >= 0 and time_from >= 0:
                        valid_connection_count += 1
                        break
            
            if valid_connection_count >= 1:
                valid_attractions.append(attraction)
            else:
                print(f"ERROR: Attraction '{attraction.name}' has no valid connections")
                attraction_problems += 1
        
        print(f"Found {len(valid_attractions)}/{len(self.attractions)} valid attractions")
        
        print(f"Validating {len(self.hotels)} hotels...")
        hotel_problems = 0
        self.working_hotels = []
        
        sample_attractions = valid_attractions if valid_attractions else self.attractions
        sample_attractions = random.sample(sample_attractions, min(15, len(sample_attractions)))
        
        for hotel in self.hotels:
            valid_connection_count = 0
            
            for attr in sample_attractions:
                for mode in [TransportMode.CAR, TransportMode.BUS_WALK, TransportMode.SUBWAY_WALK, TransportMode.WALK]:
                    time_to = Transport.get_travel_time(hotel.name, attr.name, mode)
                    time_from = Transport.get_travel_time(attr.name, hotel.name, mode)
                    
                    if time_to >= 0 and time_from >= 0:
                        valid_connection_count += 1
                        break
            
            if valid_connection_count >= 1:
                self.working_hotels.append(hotel)
            else:
                print(f"ERROR: Hotel '{hotel.name}' has no valid connections")
                hotel_problems += 1
        
        self.working_hotels.sort(key=lambda h: h.rating, reverse=True)
        
        print(f"Found {len(self.working_hotels)}/{len(self.hotels)} working hotels")
        
        if (attraction_problems > 0 or hotel_problems > 0) and valid_attractions and self.working_hotels:
            print(f"Found {attraction_problems} attraction problems and {hotel_problems} hotel problems.")
            print(f"Will continue with {len(valid_attractions)} valid attractions and {len(self.working_hotels)} working hotels.")
            return True
        
        if not valid_attractions or not self.working_hotels:
            raise RuntimeError(f"ERROR: Cannot proceed - found only {len(valid_attractions)} valid attractions and {len(self.working_hotels)} working hotels.")
        
        return True
    
    def generate_initial_population(self, population_size=100) -> List[Solution]:
        solutions = []
        start_time = time.time()
        
        attempt_count = 0
        max_attempts = population_size * 10
        
        print(f"Starting solution generation with {len(self.working_hotels)} compatible hotels")
        
        
        print("Generating solutions prioritizing maximum attractions...")
        for _ in range(population_size // 5):
            solution = self._generate_max_attractions_solution()
            if solution:
                solutions.append(solution)
                print(f"Generated solution with {solution.get_objectives()[0]} attractions")
        
        print("Generating solutions prioritizing maximum quality...")
        for _ in range(population_size // 5):
            solution = self._generate_max_quality_solution()
            if solution:
                solutions.append(solution)
                print(f"Generated solution with quality rating {solution.get_objectives()[1]:.1f}")
        
        print("Generating solutions prioritizing minimum travel time...")
        for _ in range(population_size // 5):
            solution = self._generate_min_time_solution()
            if solution:
                solutions.append(solution)
                print(f"Generated solution with travel time {solution.get_objectives()[2]:.1f} minutes")
        
        print("Generating solutions prioritizing minimum cost...")
        for _ in range(population_size // 5):
            solution = self._generate_min_cost_solution()
            if solution:
                solutions.append(solution)
                print(f"Generated solution with cost CA$ {solution.get_objectives()[3]:.2f}")
        
        print("Generating random solutions...")
        
        while len(solutions) < population_size and attempt_count < max_attempts:
            attempt_count += 1
            
            try:
                hotel = random.choice(self.working_hotels)
                
                assigned_attractions = set()
                
                day1_route = DailyRoute(is_saturday=True)
                day2_route = DailyRoute(is_saturday=False)
                
                day1_route.set_hotel(hotel)
                day2_route.set_hotel(hotel)
                
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
                        
                        total_attractions = day1_route.get_num_attractions() + day2_route.get_num_attractions()
                        if total_attractions > 0:
                            solution.objectives = solution.calculate_objectives()
                            solutions.append(solution)
                            
                            if len(solutions) % 10 == 0:
                                print(f"Generated solution {len(solutions)}/{population_size} with {total_attractions} attractions")
            except Exception as e:
                print(f"Error generating solution: {str(e)}")
            
            if attempt_count % 100 == 0:
                elapsed = time.time() - start_time
                print(f"Attempts: {attempt_count}, Solutions: {len(solutions)}/{population_size}, Time: {elapsed:.2f}s")
        
        elapsed = time.time() - start_time
        print(f"Generated {len(solutions)} valid solutions in {elapsed:.2f} seconds.")
        
        return solutions
    
    def _generate_max_attractions_solution(self) -> Optional[Solution]:
        for _ in range(min(10, len(self.working_hotels))):
            hotel = random.choice(self.working_hotels[:10])
            
            assigned_attractions = set()
            
            day1_route = DailyRoute(is_saturday=True)
            day2_route = DailyRoute(is_saturday=False)
            
            day1_route.set_hotel(hotel)
            day2_route.set_hotel(hotel)
            
            day1_success = self._generate_day_route_max_attractions(
                day1_route, 
                assigned_attractions
            )
            
            if day1_success:
                for attr in day1_route.get_attractions():
                    assigned_attractions.add(attr.name)
                
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
        top_hotels = sorted(self.working_hotels, key=lambda h: h.rating, reverse=True)[:5]
        hotel = random.choice(top_hotels)
        
        assigned_attractions = set()
        
        day1_route = DailyRoute(is_saturday=True)
        day2_route = DailyRoute(is_saturday=False)
        
        day1_route.set_hotel(hotel)
        day2_route.set_hotel(hotel)
        
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
        
        return self._generate_random_solution()
    
    def _generate_min_time_solution(self) -> Optional[Solution]:
        for _ in range(min(10, len(self.working_hotels))):
            hotel = random.choice(self.working_hotels)
            
            assigned_attractions = set()
            
            day1_route = DailyRoute(is_saturday=True)
            day2_route = DailyRoute(is_saturday=False)
            
            day1_route.set_hotel(hotel)
            day2_route.set_hotel(hotel)
            
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
        cheap_hotels = sorted(self.working_hotels, key=lambda h: h.price)[:5]
        hotel = random.choice(cheap_hotels)
        
        assigned_attractions = set()
        
        day1_route = DailyRoute(is_saturday=True)
        day2_route = DailyRoute(is_saturday=False)
        
        day1_route.set_hotel(hotel)
        day2_route.set_hotel(hotel)
        
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
        
        return self._generate_random_solution()
    
    def _generate_random_solution(self) -> Optional[Solution]:
        hotel = random.choice(self.working_hotels)
        
        assigned_attractions = set()
        
        day1_route = DailyRoute(is_saturday=True)
        day2_route = DailyRoute(is_saturday=False)
        
        day1_route.set_hotel(hotel)
        day2_route.set_hotel(hotel)
        
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
        hotel = day_route.hotel
        is_saturday = day_route.is_saturday
        day_key = "saturday" if is_saturday else "sunday"
        
        used_attraction_names = set(assigned_attractions)
        
        max_attractions = 5
        
        while day_route.get_num_attractions() < max_attractions:
            if day_route.get_num_attractions() == 0:
                from_name = hotel.name
                is_from_hotel = True
            else:
                from_name = day_route.get_attractions()[-1].name
                is_from_hotel = False
            
            candidates = self._find_next_attraction_candidates(
                from_name, 
                is_from_hotel, 
                hotel.name, 
                is_saturday, 
                used_attraction_names
            )
            
            if not candidates:
                break
            
            selected = random.choice(candidates)
            
            if not day_route.add_attraction(selected["attraction"], selected["to_mode"]):
                used_attraction_names.add(selected["attraction"].name)
                continue
            
            used_attraction_names.add(selected["attraction"].name)
        
        if day_route.get_num_attractions() > 0:
            last_attraction = day_route.get_attractions()[-1]
            
            valid_return_modes = day_route.get_valid_return_modes()
            
            if not valid_return_modes:
                if (last_attraction.name in self._attraction_hotel_compatibility and 
                    hotel.name in self._attraction_hotel_compatibility[last_attraction.name]):
                    valid_return_modes = self._attraction_hotel_compatibility[last_attraction.name][hotel.name]
            
            if not valid_return_modes:
                return False
            
            return_mode = random.choice(valid_return_modes)
            if not day_route.set_return_mode(return_mode):
                return False
        
        return day_route.get_num_attractions() > 0 and day_route.is_valid()
    
    def _generate_day_route_max_attractions(self, day_route: DailyRoute, 
                                          assigned_attractions: Set[str]) -> bool:
        hotel = day_route.hotel
        is_saturday = day_route.is_saturday
        day_key = "saturday" if is_saturday else "sunday"
        
        used_attraction_names = set(assigned_attractions)
        
        available_attractions = (self.saturday_open_attractions if is_saturday 
                               else self.sunday_open_attractions)
        
        available_attractions = [attr for attr in available_attractions 
                               if attr.name not in used_attraction_names]
        
        available_attractions.sort(key=lambda a: a.visit_time)
        
        for attr in available_attractions:
            if attr.name in used_attraction_names:
                continue
            
            if day_route.get_num_attractions() == 0:
                from_name = hotel.name
            else:
                from_name = day_route.get_attractions()[-1].name
            
            valid_modes = self._get_valid_transport_modes(from_name, attr.name)
            if not valid_modes:
                continue
            
            if (attr.name in self._attraction_hotel_compatibility and 
                hotel.name in self._attraction_hotel_compatibility[attr.name]):
                
                to_mode = self._choose_preferred_mode(valid_modes)
                
                if day_route.add_attraction(attr, to_mode):
                    used_attraction_names.add(attr.name)
                    
                    if day_route.get_num_attractions() >= 5:
                        break
        
        if day_route.get_num_attractions() > 0:
            last_attraction = day_route.get_attractions()[-1]
            valid_return_modes = self._get_valid_transport_modes(last_attraction.name, hotel.name)
            
            if valid_return_modes:
                return_mode = self._choose_preferred_mode(valid_return_modes)
                day_route.set_return_mode(return_mode)
        
        return day_route.get_num_attractions() > 0 and day_route.is_valid()
    
    def _generate_day_route_max_quality(self, day_route: DailyRoute, 
                                       assigned_attractions: Set[str]) -> bool:
        hotel = day_route.hotel
        is_saturday = day_route.is_saturday
        
        used_attraction_names = set(assigned_attractions)
        
        available_attractions = (self.saturday_open_attractions if is_saturday 
                               else self.sunday_open_attractions)
        
        available_attractions = [attr for attr in available_attractions 
                               if attr.name not in used_attraction_names]
        
        available_attractions.sort(key=lambda a: a.rating, reverse=True)
        
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
            
            if (attr.name in self._attraction_hotel_compatibility and 
                hotel.name in self._attraction_hotel_compatibility[attr.name]):
                
                to_mode = self._choose_preferred_mode(valid_modes)
                
                if day_route.add_attraction(attr, to_mode):
                    used_attraction_names.add(attr.name)
                    
                    if day_route.get_num_attractions() >= 3:
                        break
        
        if day_route.get_num_attractions() < 5:
            remaining = list(available_attractions)
            random.shuffle(remaining)
            
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
        
        if day_route.get_num_attractions() > 0:
            last_attraction = day_route.get_attractions()[-1]
            valid_return_modes = self._get_valid_transport_modes(last_attraction.name, hotel.name)
            
            if valid_return_modes:
                return_mode = self._choose_preferred_mode(valid_return_modes)
                day_route.set_return_mode(return_mode)
        
        return day_route.get_num_attractions() > 0 and day_route.is_valid()
    
    def _generate_day_route_min_time(self, day_route: DailyRoute, 
                                    assigned_attractions: Set[str]) -> bool:
        hotel = day_route.hotel
        is_saturday = day_route.is_saturday
        
        used_attraction_names = set(assigned_attractions)
        
        available_attractions = (self.saturday_open_attractions if is_saturday 
                               else self.sunday_open_attractions)
        
        available_attractions = [attr for attr in available_attractions 
                               if attr.name not in used_attraction_names]
        
        hotel_close_attractions = []
        for attr in available_attractions:
            travel_time = Transport.get_travel_time(hotel.name, attr.name, TransportMode.WALK)
            if travel_time >= 0 and travel_time < 30:
                hotel_close_attractions.append((attr, travel_time))
        
        hotel_close_attractions.sort(key=lambda x: x[1])
        
        if hotel_close_attractions:
            attr, _ = random.choice(hotel_close_attractions[:3])
            
            if day_route.add_attraction(attr, TransportMode.WALK):
                used_attraction_names.add(attr.name)
        
        if day_route.get_num_attractions() == 0:
            for attr in available_attractions:
                valid_modes = self._get_valid_transport_modes(hotel.name, attr.name)
                if not valid_modes:
                    continue
                
                to_mode = min(valid_modes, key=lambda m: Transport.get_travel_time(hotel.name, attr.name, m))
                
                if day_route.add_attraction(attr, to_mode):
                    used_attraction_names.add(attr.name)
                    break
        
        while day_route.get_num_attractions() < 3:
            if day_route.get_num_attractions() == 0:
                break
            
            last_attr = day_route.get_attractions()[-1]
            
            close_attractions = []
            for attr in available_attractions:
                if attr.name in used_attraction_names:
                    continue
                
                travel_time = Transport.get_travel_time(last_attr.name, attr.name, TransportMode.WALK)
                if travel_time >= 0:
                    close_attractions.append((attr, travel_time))
            
            close_attractions.sort(key=lambda x: x[1])
            
            added = False
            for attr, _ in close_attractions[:5]:
                if day_route.add_attraction(attr, TransportMode.WALK):
                    used_attraction_names.add(attr.name)
                    added = True
                    break
            
            if not added:
                break
        
        if day_route.get_num_attractions() > 0:
            last_attraction = day_route.get_attractions()[-1]
            valid_return_modes = self._get_valid_transport_modes(last_attraction.name, hotel.name)
            
            if valid_return_modes:
                return_mode = min(valid_return_modes, 
                                key=lambda m: Transport.get_travel_time(last_attraction.name, hotel.name, m))
                day_route.set_return_mode(return_mode)
        
        return day_route.get_num_attractions() > 0 and day_route.is_valid()
    
    def _generate_day_route_min_cost(self, day_route: DailyRoute, 
                                   assigned_attractions: Set[str]) -> bool:
        hotel = day_route.hotel
        is_saturday = day_route.is_saturday
        
        used_attraction_names = set(assigned_attractions)
        
        available_attractions = (self.saturday_open_attractions if is_saturday 
                               else self.sunday_open_attractions)
        
        available_attractions = [attr for attr in available_attractions 
                               if attr.name not in used_attraction_names]
        
        available_attractions.sort(key=lambda a: a.cost)
        
        free_attractions = [attr for attr in available_attractions if attr.cost == 0]
        
        for attr in free_attractions:
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
                
                if day_route.get_num_attractions() >= 4:
                    break
        
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
        
        if day_route.get_num_attractions() > 0:
            last_attraction = day_route.get_attractions()[-1]
            valid_return_modes = self._get_valid_transport_modes(last_attraction.name, hotel.name)
            
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
        day_key = "saturday" if is_saturday else "sunday"
        candidates = []
        available_attractions = self.saturday_open_attractions if is_saturday else self.sunday_open_attractions
        
        if is_from_hotel:
            if hotel_name in self._hotel_attraction_compatibility:
                for attr_name, compat_data in self._hotel_attraction_compatibility[hotel_name].items():
                    if attr_name in used_attractions or day_key not in compat_data:
                        continue
                    
                    attr = next((a for a in available_attractions if a.name == attr_name), None)
                    if not attr:
                        continue
                    
                    valid_to_modes = compat_data[day_key]
                    
                    has_return_path = False
                    if (attr_name in self._attraction_hotel_compatibility and 
                        hotel_name in self._attraction_hotel_compatibility[attr_name]):
                        has_return_path = len(self._attraction_hotel_compatibility[attr_name][hotel_name]) > 0
                    
                    if has_return_path:
                        for to_mode in valid_to_modes:
                            candidates.append({
                                "attraction": attr,
                                "to_mode": to_mode,
                            })
        
        else:
            if from_name in self._attraction_compatibility_matrix:
                for next_attr_name, compat_data in self._attraction_compatibility_matrix[from_name].items():
                    if next_attr_name in used_attractions or day_key not in compat_data:
                        continue
                    
                    next_attr = next((a for a in available_attractions if a.name == next_attr_name), None)
                    if not next_attr:
                        continue
                    
                    valid_to_modes = compat_data[day_key]
                    
                    has_return_path = False
                    if (next_attr_name in self._attraction_hotel_compatibility and 
                        hotel_name in self._attraction_hotel_compatibility[next_attr_name]):
                        has_return_path = len(self._attraction_hotel_compatibility[next_attr_name][hotel_name]) > 0
                    
                    if has_return_path:
                        for to_mode in valid_to_modes:
                            candidates.append({
                                "attraction": next_attr,
                                "to_mode": to_mode,
                            })
        
        return candidates
    
    def _get_valid_transport_modes(self, from_name: str, to_name: str) -> List[TransportMode]:
        from utils import Transport
        
        valid_modes = []
        for mode in [TransportMode.WALK, TransportMode.BUS_WALK, TransportMode.SUBWAY_WALK, TransportMode.CAR]:
            if Transport.get_travel_time(from_name, to_name, mode) >= 0:
                valid_modes.append(mode)
        
        return valid_modes
    
    def _choose_preferred_mode(self, valid_modes: List[TransportMode]) -> TransportMode:
        if not valid_modes:
            return TransportMode.CAR
        
        if TransportMode.WALK in valid_modes:
            return TransportMode.WALK
        
        if TransportMode.SUBWAY_WALK in valid_modes:
            return TransportMode.SUBWAY_WALK
        
        if TransportMode.BUS_WALK in valid_modes:
            return TransportMode.BUS_WALK
        
        if TransportMode.CAR in valid_modes:
            return TransportMode.CAR
        
        return valid_modes[0]