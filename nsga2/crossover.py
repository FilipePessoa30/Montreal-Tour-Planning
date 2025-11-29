import copy
import random
from typing import List, Set, Tuple
from models import Solution, DailyRoute, Attraction, TransportMode
from utils import Transport, Config

class Crossover:
    def __init__(self, constructor):
        self.constructor = constructor

    def crossover(self, parent1: Solution, parent2: Solution) -> Tuple[Solution, Solution]:
        child1 = self._create_child_ox(parent1, parent2)
        child2 = self._create_child_ox(parent2, parent1)
        if child1 is None:
            child1 = copy.deepcopy(parent1)
        if child2 is None:
            child2 = copy.deepcopy(parent2)
        child1.objectives = child1.calculate_objectives()
        child2.objectives = child2.calculate_objectives()
        return child1, child2

    def _create_child_ox(self, parent1: Solution, parent2: Solution) -> Solution:
        if random.random() < 0.5:
            new_hotel = parent1.hotel
        else:
            new_hotel = parent2.hotel
        day1_route = self._ox_day_route(parent1.day1_route, parent2.day1_route, new_hotel, True, set())
        used_attrs = {a.name for a in day1_route.get_attractions()}
        day2_route = self._ox_day_route(parent1.day2_route, parent2.day2_route, new_hotel, False, used_attrs)
        if day1_route.get_num_attractions() == 0 and day2_route.get_num_attractions() == 0:
            return None
        child = Solution(new_hotel, day1_route, day2_route)
        return child

    def _ox_day_route(self, route1: DailyRoute, route2: DailyRoute, hotel, is_saturday: bool, used_attrs: Set[str]) -> DailyRoute:
        new_route = DailyRoute(is_saturday=is_saturday)
        new_route.set_hotel(hotel)
        attrs1 = [a for a in route1.get_attractions() if a.name not in used_attrs and a.is_open_on_day(is_saturday)]
        attrs2 = [a for a in route2.get_attractions() if a.name not in used_attrs and a.is_open_on_day(is_saturday)]
        if len(attrs1) < 2 and len(attrs2) < 2:
            combined = []
            for a in attrs1:
                if a.name not in [x.name for x in combined]:
                    combined.append(a)
            for a in attrs2:
                if a.name not in [x.name for x in combined]:
                    combined.append(a)
            for attr in combined:
                self._try_add_attraction(new_route, attr)
            return new_route
        if len(attrs1) >= 2:
            p1_len = len(attrs1)
            cut1 = random.randint(0, p1_len - 1)
            cut2 = random.randint(0, p1_len - 1)
            if cut1 > cut2:
                cut1, cut2 = cut2, cut1
            segment = attrs1[cut1:cut2 + 1]
            for attr in segment:
                self._try_add_attraction(new_route, attr)
            segment_names = {a.name for a in segment}
            remaining = [a for a in attrs2 if a.name not in segment_names]
            for attr in remaining:
                self._try_add_attraction(new_route, attr)
        else:
            for attr in attrs2:
                self._try_add_attraction(new_route, attr)
        return new_route

    def _try_add_attraction(self, route: DailyRoute, attraction: Attraction) -> bool:
        if not attraction.is_open_on_day(route.is_saturday):
            return False
        if route.get_num_attractions() == 0:
            from_name = route.hotel.name
        else:
            from_name = route.attractions[-1].name
        to_modes = self._get_valid_transport_modes(from_name, attraction.name)
        if not to_modes:
            return False
        return_modes = self._get_valid_transport_modes(attraction.name, route.hotel.name)
        if not return_modes:
            return False
        to_mode = self._choose_preferred_transport_mode(to_modes, from_name, attraction.name)
        return_mode = self._choose_preferred_transport_mode(return_modes, attraction.name, route.hotel.name)
        original_attractions = route.attractions.copy()
        original_transport_modes = route.transport_modes.copy()
        if route.attractions:
            route.attractions.append(attraction)
            if len(route.transport_modes) > len(route.attractions) - 1:
                route.transport_modes = route.transport_modes[:-1] + [to_mode, return_mode]
            else:
                route.transport_modes.append(to_mode)
                route.transport_modes.append(return_mode)
        else:
            route.attractions = [attraction]
            route.transport_modes = [to_mode, return_mode]
        route.recalculate_time_info()
        if route.is_valid():
            return True
        route.attractions = original_attractions
        route.transport_modes = original_transport_modes
        route.recalculate_time_info()
        return False

    def _get_valid_transport_modes(self, from_name: str, to_name: str) -> List[TransportMode]:
        valid_modes = []
        for mode in [TransportMode.WALK, TransportMode.BUS_WALK, TransportMode.SUBWAY_WALK, TransportMode.CAR]:
            travel_time = Transport.get_travel_time(from_name, to_name, mode)
            if travel_time >= 0:
                valid_modes.append(mode)
        return valid_modes

    def _choose_preferred_transport_mode(self, valid_modes: List[TransportMode], from_name: str, to_name: str) -> TransportMode:
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
        if TransportMode.CAR in valid_modes:
            return TransportMode.CAR
        return valid_modes[0]
