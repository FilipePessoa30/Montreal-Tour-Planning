from dataclasses import dataclass
from typing import List, Optional, Set
from enum import Enum

class TransportMode(Enum):
    WALK = 0
    SUBWAY_WALK = 1
    BUS_WALK = 2
    CAR = 3

class LocationType(Enum):
    HOTEL = 0
    ATTRACTION = 1

@dataclass
class TimeInfo:
    location_type: LocationType
    arrival_time: float
    wait_time: float
    departure_time: float

@dataclass
class Hotel:
    name: str
    price: float
    rating: float

@dataclass
class Attraction:
    name: str
    neighborhood: str
    visit_time: int
    cost: float
    saturday_opening_time: int
    saturday_closing_time: int
    sunday_opening_time: int
    sunday_closing_time: int
    rating: float

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if not isinstance(other, Attraction):
            return False
        return self.name == other.name

    def is_open_on_day(self, is_saturday: bool) -> bool:
        opening_time = self.saturday_opening_time if is_saturday else self.sunday_opening_time
        closing_time = self.saturday_closing_time if is_saturday else self.sunday_closing_time
        return opening_time != -1 and closing_time != -1

    def get_opening_time(self, is_saturday: bool) -> int:
        return self.saturday_opening_time if is_saturday else self.sunday_opening_time

    def get_closing_time(self, is_saturday: bool) -> int:
        return self.saturday_closing_time if is_saturday else self.sunday_closing_time

class DailyRoute:
    def __init__(self, is_saturday: bool):
        self.is_saturday = is_saturday
        self.hotel = None
        self.attractions: List[Attraction] = []
        self.transport_modes: List[TransportMode] = []
        self.time_info: List[TimeInfo] = []
        self.start_time = 8 * 60
        self.end_time = 20 * 60

    def set_hotel(self, hotel: Hotel):
        self.hotel = hotel
        self.recalculate_time_info()

    def get_attractions(self) -> List[Attraction]:
        return self.attractions

    def get_transport_modes(self) -> List[TransportMode]:
        return self.transport_modes

    def get_num_attractions(self) -> int:
        return len(self.attractions)

    def get_total_time(self) -> float:
        if not self.attractions or not self.hotel or not self.time_info or len(self.time_info) < 2:
            return 0.0
        return self.time_info[-1].arrival_time - self.time_info[0].departure_time

    def get_total_cost(self) -> float:
        from utils import Transport, Config
        total_cost = sum(attr.cost for attr in self.attractions)
        if self.hotel and self.attractions:
            if self.transport_modes and len(self.transport_modes) > 0 and self.transport_modes[0] == TransportMode.CAR:
                travel_time = Transport.get_travel_time(self.hotel.name, self.attractions[0].name, TransportMode.CAR)
                if travel_time > 0:
                    total_cost += travel_time * Config.CAR_COST_PER_MINUTE
            for i in range(len(self.attractions) - 1):
                if i + 1 < len(self.transport_modes) and self.transport_modes[i + 1] == TransportMode.CAR:
                    travel_time = Transport.get_travel_time(self.attractions[i].name, self.attractions[i + 1].name, TransportMode.CAR)
                    if travel_time > 0:
                        total_cost += travel_time * Config.CAR_COST_PER_MINUTE
            if len(self.transport_modes) > len(self.attractions):
                return_mode = self.transport_modes[len(self.attractions)]
                if return_mode == TransportMode.CAR:
                    travel_time = Transport.get_travel_time(self.attractions[-1].name, self.hotel.name, TransportMode.CAR)
                    if travel_time > 0:
                        total_cost += travel_time * Config.CAR_COST_PER_MINUTE
        return total_cost

    def get_total_rating(self) -> float:
        if not self.attractions:
            return 0.0
        return sum(attr.rating for attr in self.attractions)

    def get_neighborhoods(self) -> Set[str]:
        return {attr.neighborhood for attr in self.attractions}

    def can_add_attraction(self, attraction: Attraction, mode: TransportMode):
        from utils import Transport
        if not self.hotel:
            return False, 0, 0
        if not self.attractions:
            current_time = self.start_time
            from_name = self.hotel.name
        else:
            if len(self.time_info) <= len(self.attractions):
                self.recalculate_time_info()
                if not self.time_info or len(self.time_info) <= len(self.attractions):
                    return False, 0, 0
            current_time = self.time_info[len(self.attractions)].departure_time
            from_name = self.attractions[-1].name
        travel_time = Transport.get_travel_time(from_name, attraction.name, mode)
        if travel_time < 0:
            return False, 0, 0
        current_time += travel_time
        if not attraction.is_open_on_day(self.is_saturday):
            return False, 0, 0
        opening_time = attraction.get_opening_time(self.is_saturday)
        closing_time = attraction.get_closing_time(self.is_saturday)
        if current_time < opening_time:
            current_time = opening_time
        arrival_time = current_time
        if current_time >= closing_time:
            return False, 0, 0
        visit_end_time = current_time + attraction.visit_time
        if visit_end_time > closing_time:
            return False, 0, 0
        if visit_end_time > self.end_time:
            return False, 0, 0
        departure_time = visit_end_time
        return True, arrival_time, departure_time

    def add_attraction(self, attraction: Attraction, mode: TransportMode) -> bool:
        if not self.hotel:
            return False
        is_feasible, arrival_time, departure_time = self.can_add_attraction(attraction, mode)
        if not is_feasible:
            return False
        self.attractions.append(attraction)
        self.transport_modes.append(mode)
        if len(self.attractions) == 1:
            self.transport_modes.append(TransportMode.CAR)
        self.recalculate_time_info()
        if not self.is_valid():
            self.attractions.pop()
            if len(self.transport_modes) == 2 and len(self.attractions) == 0:
                self.transport_modes = []
            else:
                self.transport_modes.pop()
            self.recalculate_time_info()
            return False
        return True

    def set_return_mode(self, mode: TransportMode) -> bool:
        from utils import Transport
        if not self.hotel or not self.attractions:
            return False
        old_mode = self.transport_modes[-1] if len(self.transport_modes) > len(self.attractions) else None
        if len(self.transport_modes) > len(self.attractions):
            self.transport_modes[-1] = mode
        else:
            self.transport_modes.append(mode)
        self.recalculate_time_info()
        if not self.is_valid():
            if old_mode is not None:
                self.transport_modes[-1] = old_mode
            else:
                if len(self.transport_modes) > len(self.attractions):
                    self.transport_modes.pop()
            self.recalculate_time_info()
            return False
        return True

    def get_valid_return_modes(self) -> List[TransportMode]:
        from utils import Transport
        if not self.hotel or not self.attractions:
            return []
        if len(self.time_info) <= len(self.attractions):
            self.recalculate_time_info()
            if not self.time_info or len(self.time_info) <= len(self.attractions):
                return []
        last_departure_time = self.time_info[len(self.attractions)].departure_time
        valid_modes = []
        for mode in [TransportMode.WALK, TransportMode.BUS_WALK, TransportMode.SUBWAY_WALK, TransportMode.CAR]:
            travel_time = Transport.get_travel_time(self.attractions[-1].name, self.hotel.name, mode)
            if travel_time < 0:
                continue
            if last_departure_time + travel_time <= self.end_time:
                valid_modes.append(mode)
        return valid_modes

    def recalculate_time_info(self):
        from utils import Transport
        if not self.hotel:
            self.time_info = []
            return
        temp_time_info = [None] * (len(self.attractions) + 2)
        current_time = self.start_time
        temp_time_info[0] = TimeInfo(
            location_type=LocationType.HOTEL,
            arrival_time=current_time,
            wait_time=0,
            departure_time=current_time
        )
        for i, attraction in enumerate(self.attractions):
            if i >= len(self.transport_modes):
                return
            mode = self.transport_modes[i]
            if i == 0:
                from_name = self.hotel.name
            else:
                from_name = self.attractions[i - 1].name
            travel_time = Transport.get_travel_time(from_name, attraction.name, mode)
            if travel_time < 0:
                return
            current_time += travel_time
            if not attraction.is_open_on_day(self.is_saturday):
                return
            opening_time = attraction.get_opening_time(self.is_saturday)
            closing_time = attraction.get_closing_time(self.is_saturday)
            wait_time = 0.0
            if current_time < opening_time:
                wait_time = opening_time - current_time
                current_time = opening_time
            if current_time >= closing_time:
                return
            temp_time_info[i + 1] = TimeInfo(
                location_type=LocationType.ATTRACTION,
                arrival_time=current_time,
                wait_time=wait_time,
                departure_time=current_time + attraction.visit_time
            )
            current_time += attraction.visit_time
            if current_time > closing_time:
                return
        if self.attractions:
            if len(self.transport_modes) <= len(self.attractions):
                return
            mode = self.transport_modes[len(self.attractions)]
            travel_time = Transport.get_travel_time(self.attractions[-1].name, self.hotel.name, mode)
            if travel_time < 0:
                return
            current_time += travel_time
            if current_time > self.end_time:
                return
            temp_time_info[-1] = TimeInfo(
                location_type=LocationType.HOTEL,
                arrival_time=current_time,
                wait_time=0,
                departure_time=current_time
            )
        if all(entry is not None for entry in temp_time_info):
            self.time_info = temp_time_info
        else:
            self.time_info = []

    def is_valid(self) -> bool:
        if not self.hotel:
            return False
        if not self.attractions:
            return True
        if not self.time_info:
            return False
        if len(self.time_info) != len(self.attractions) + 2:
            return False
        for i, attraction in enumerate(self.attractions):
            if not attraction.is_open_on_day(self.is_saturday):
                return False
            info = self.time_info[i + 1]
            if not info:
                return False
            opening_time = attraction.get_opening_time(self.is_saturday)
            closing_time = attraction.get_closing_time(self.is_saturday)
            if info.arrival_time < opening_time or info.arrival_time >= closing_time:
                return False
            if info.departure_time > closing_time:
                return False
        if self.time_info[-1].arrival_time > self.end_time:
            return False
        return True

class Solution:
    def __init__(self, hotel: Hotel, day1_route: DailyRoute, day2_route: DailyRoute):
        self.hotel = hotel
        self.day1_route = day1_route
        self.day2_route = day2_route
        self.objectives = self.calculate_objectives()
        self.rank = 0
        self.crowding_distance = 0
        self.domination_count = 0
        self.dominated_solutions = []

    def get_objectives(self) -> List[float]:
        return self.objectives

    def calculate_objectives(self) -> List[float]:
        total_attractions = self.day1_route.get_num_attractions() + self.day2_route.get_num_attractions()
        total_rating = self.day1_route.get_total_rating() + self.day2_route.get_total_rating()
        if self.hotel:
            total_rating += self.hotel.rating * 2
        if total_attractions == 0:
            total_rating = 0.0
        total_time = self.day1_route.get_total_time() + self.day2_route.get_total_time()
        total_cost = self.day1_route.get_total_cost() + self.day2_route.get_total_cost()
        if self.hotel:
            total_cost += self.hotel.price
        return [total_attractions, total_rating, total_time, total_cost]
