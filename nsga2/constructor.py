import random
from typing import List, Dict, Set, Optional
from models import Attraction, Hotel, DailyRoute, TransportMode, Solution
from utils import Parser, Transport

class RouteConstructor:
    def __init__(self, attractions_file: str, hotels_file: str, matrices_path: str):
        self.attractions = Parser.load_attractions(attractions_file)
        self.hotels = Parser.load_hotels(hotels_file)
        success = Parser.load_transport_matrices(matrices_path)
        if not success:
            raise RuntimeError("Failed to load transport matrices")
        self.attraction_by_name = {attr.name: attr for attr in self.attractions}
        self.hotel_by_name = {hotel.name: hotel for hotel in self.hotels}
        self.working_hotels = []
        self.saturday_open_attractions = []
        self.sunday_open_attractions = []
        for attr in self.attractions:
            if attr.is_open_on_day(True):
                self.saturday_open_attractions.append(attr)
            if attr.is_open_on_day(False):
                self.sunday_open_attractions.append(attr)
        self._hotel_attraction_compatibility = {}
        self._attraction_hotel_compatibility = {}
        self._attraction_compatibility_matrix = {}
        self._build_compatibility_matrices()
        self._validate_hotels()

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
                    self._hotel_attraction_compatibility[hotel.name][attr.name] = {"saturday": valid_modes, "modes": valid_modes}
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
        for attr in self.attractions:
            if attr.name not in self._attraction_hotel_compatibility:
                self._attraction_hotel_compatibility[attr.name] = {}
            for hotel in self.hotels:
                valid_return_modes = []
                for mode in [TransportMode.CAR, TransportMode.BUS_WALK, TransportMode.SUBWAY_WALK, TransportMode.WALK]:
                    travel_time = Transport.get_travel_time(attr.name, hotel.name, mode)
                    if travel_time >= 0:
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
                                earliest_arrival = earliest_departure + travel_time
                                if earliest_arrival < to_attr.sunday_closing_time:
                                    if earliest_arrival < to_attr.sunday_opening_time:
                                        earliest_arrival = to_attr.sunday_opening_time
                                    if earliest_arrival + to_attr.visit_time <= to_attr.sunday_closing_time:
                                        sun_valid_modes.append(mode)
                    if sat_valid_modes or sun_valid_modes:
                        self._attraction_compatibility_matrix[from_attr.name][to_attr.name] = {"saturday": sat_valid_modes, "sunday": sun_valid_modes}

    def _validate_hotels(self):
        self.working_hotels = []
        sample_attractions = random.sample(self.attractions, min(15, len(self.attractions)))
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
        self.working_hotels.sort(key=lambda h: h.rating, reverse=True)

    def generate_initial_population(self, population_size: int = 100, mandatory_attractions: List[int] = None) -> List[Solution]:
        solutions = []
        mandatory_attrs = []
        if mandatory_attractions:
            for idx in mandatory_attractions:
                if 0 <= idx < len(self.attractions):
                    mandatory_attrs.append(self.attractions[idx])
            mandatory_attrs = mandatory_attrs[:2]
        attempt_count = 0
        max_attempts = population_size * 100
        while len(solutions) < population_size and attempt_count < max_attempts:
            attempt_count += 1
            hotel = random.choice(self.working_hotels)
            assigned_attractions = set()
            day1_route = DailyRoute(is_saturday=True)
            day2_route = DailyRoute(is_saturday=False)
            day1_route.set_hotel(hotel)
            day2_route.set_hotel(hotel)
            day1_success = self._generate_day_route(day1_route, assigned_attractions, 0 if mandatory_attrs else None, mandatory_attrs)
            if day1_success:
                for attr in day1_route.get_attractions():
                    assigned_attractions.add(attr.name)
                day2_success = self._generate_day_route(day2_route, assigned_attractions, 1 if len(mandatory_attrs) > 1 else None, mandatory_attrs)
                if day2_success:
                    solution = Solution(hotel, day1_route, day2_route)
                    total_attractions = day1_route.get_num_attractions() + day2_route.get_num_attractions()
                    if total_attractions > 0:
                        solution.objectives = solution.calculate_objectives()
                        solutions.append(solution)
        solutions.sort(key=lambda s: (s.get_objectives()[0], s.get_objectives()[1]), reverse=True)
        return solutions

    def _generate_day_route(self, day_route: DailyRoute, assigned_attractions: Set[str], mandatory_idx: Optional[int] = None, mandatory_attractions: List[Attraction] = None) -> bool:
        hotel = day_route.hotel
        is_saturday = day_route.is_saturday
        day_key = "saturday" if is_saturday else "sunday"
        used_attraction_names = set(assigned_attractions)
        if mandatory_idx is not None and mandatory_attractions and mandatory_idx < len(mandatory_attractions):
            mandatory_attr = mandatory_attractions[mandatory_idx]
            if mandatory_attr.name in used_attraction_names:
                return False
            if not mandatory_attr.is_open_on_day(is_saturday):
                return False
            if hotel.name not in self._hotel_attraction_compatibility or mandatory_attr.name not in self._hotel_attraction_compatibility[hotel.name] or day_key not in self._hotel_attraction_compatibility[hotel.name][mandatory_attr.name]:
                return False
            valid_to_modes = self._hotel_attraction_compatibility[hotel.name][mandatory_attr.name][day_key]
            if not valid_to_modes:
                return False
            to_mode = random.choice(valid_to_modes)
            if not day_route.add_attraction(mandatory_attr, to_mode):
                return False
            used_attraction_names.add(mandatory_attr.name)
        max_attractions = 5
        while day_route.get_num_attractions() < max_attractions:
            if day_route.get_num_attractions() == 0:
                from_name = hotel.name
                is_from_hotel = True
            else:
                from_name = day_route.get_attractions()[-1].name
                is_from_hotel = False
            candidates = self._find_next_attraction_candidates(from_name, is_from_hotel, hotel.name, is_saturday, used_attraction_names)
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
                if last_attraction.name in self._attraction_hotel_compatibility and hotel.name in self._attraction_hotel_compatibility[last_attraction.name]:
                    valid_return_modes = self._attraction_hotel_compatibility[last_attraction.name][hotel.name]
            if not valid_return_modes:
                return False
            return_mode = random.choice(valid_return_modes)
            if not day_route.set_return_mode(return_mode):
                return False
        return day_route.get_num_attractions() > 0 and day_route.is_valid()

    def _find_next_attraction_candidates(self, from_name: str, is_from_hotel: bool, hotel_name: str, is_saturday: bool, used_attractions: Set[str]) -> List[Dict]:
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
                    if attr_name in self._attraction_hotel_compatibility and hotel_name in self._attraction_hotel_compatibility[attr_name]:
                        has_return_path = len(self._attraction_hotel_compatibility[attr_name][hotel_name]) > 0
                    if has_return_path:
                        for to_mode in valid_to_modes:
                            candidates.append({"attraction": attr, "to_mode": to_mode})
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
                    if next_attr_name in self._attraction_hotel_compatibility and hotel_name in self._attraction_hotel_compatibility[next_attr_name]:
                        has_return_path = len(self._attraction_hotel_compatibility[next_attr_name][hotel_name]) > 0
                    if has_return_path:
                        for to_mode in valid_to_modes:
                            candidates.append({"attraction": next_attr, "to_mode": to_mode})
        return candidates

    def export_population(self, solutions: List[Solution], output_file: str) -> None:
        import os
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        with open(output_file, 'w', encoding='utf-8') as file:
            file.write("Solution;Hotel;TotalAttractions;TotalQuality;TotalTime;TotalCost\n")
            for i, solution in enumerate(solutions):
                solution.objectives = solution.calculate_objectives()
                objectives = solution.get_objectives()
                file.write(f"{i+1};{solution.hotel.name};{objectives[0]:.0f};{objectives[1]:.1f};{objectives[2]:.1f};{objectives[3]:.2f}\n")
