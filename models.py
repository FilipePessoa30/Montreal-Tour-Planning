"""
Data models for Montreal tour planning system.
Defines attractions, hotels, routes and solutions.
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Set
from enum import Enum
from functools import lru_cache

class TransportMode(Enum):
   WALK = 0
   SUBWAY_WALK = 1
   BUS_WALK = 2
   CAR = 3
   
   @staticmethod
   def get_mode_string(mode) -> str:
       mode_strings = {
           TransportMode.WALK: "Walking",
           TransportMode.SUBWAY_WALK: "Subway",
           TransportMode.BUS_WALK: "Bus",
           TransportMode.CAR: "Car"
       }
       return mode_strings.get(mode, "Unknown")

class LocationType(Enum):
   HOTEL = 0
   ATTRACTION = 1

@dataclass
class TimeInfo:
   location_type: LocationType
   arrival_time: float
   wait_time: float
   departure_time: float
   
   @staticmethod
   def format_time(time_in_minutes: float) -> str:
       hours = int(time_in_minutes // 60)
       minutes = int(time_in_minutes % 60)
       return f"{hours:02d}:{minutes:02d}"

@dataclass
class Hotel:
   name: str
   price: float
   rating: float
   latitude: float = 0.0
   longitude: float = 0.0
   
   def __post_init__(self):
       if self.price < 0:
           raise ValueError("Hotel price cannot be negative")
       if self.rating < 0 or self.rating > 5:
           raise ValueError("Hotel rating must be between 0 and 5")

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
   latitude: float = 0.0
   longitude: float = 0.0
   
   def __post_init__(self):
       if self.visit_time < 0:
           raise ValueError("Visit time cannot be negative")
       if self.cost < 0:
           raise ValueError("Cost cannot be negative")
       if self.rating < 0 or self.rating > 5:
           raise ValueError("Rating must be between 0 and 5")
       
       for time_val in [self.saturday_opening_time, self.saturday_closing_time, 
                        self.sunday_opening_time, self.sunday_closing_time]:
           if time_val != -1 and (time_val < 0 or time_val >= 24*60):
               raise ValueError(f"Invalid time value: {time_val}")
   
   def __hash__(self):
       return hash(self.name)
   
   def __eq__(self, other):
       if not isinstance(other, Attraction):
           return False
       return self.name == other.name
   
   @lru_cache(maxsize=100)
   def is_open_at(self, time: int, is_saturday: bool) -> bool:
       opening_time = self.saturday_opening_time if is_saturday else self.sunday_opening_time
       closing_time = self.saturday_closing_time if is_saturday else self.sunday_closing_time
       
       if opening_time == -1 or closing_time == -1:
           return False
       
       if opening_time == 0 and closing_time == 23 * 60 + 59:
           return True
       
       return opening_time <= time < closing_time
   
   @lru_cache(maxsize=2)
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
       self.return_to_hotel_mode: Optional[TransportMode] = None
       self.time_info: List[TimeInfo] = []
       self.start_time = 8 * 60
       self.end_time = 20 * 60
       
       self._attraction_compatibility_cache = {}
   
   def set_hotel(self, hotel: Hotel):
       if hotel is None:
           raise ValueError("Hotel pointer cannot be null")
       self.hotel = hotel
       self.recalculate_time_info()
       
       self._attraction_compatibility_cache.clear()
   
   def get_attractions(self) -> List[Attraction]:
       return self.attractions
   
   def get_transport_modes(self) -> List[TransportMode]:
       """
       Get all transport modes including return to hotel mode.
       """
       if not self.attractions:
           return []
           
       result = self.transport_modes.copy()
       if self.return_to_hotel_mode is not None:
           result.append(self.return_to_hotel_mode)
       return result
   
   def get_time_info(self) -> List[TimeInfo]:
       return self.time_info
   
   def get_num_attractions(self) -> int:
       return len(self.attractions)
   
   def get_total_time(self) -> float:
       """Get total time of the route in minutes"""
       if not self.attractions or not self.hotel or not self.time_info or len(self.time_info) < 2:
           return 0.0
       
       return self.time_info[-1].arrival_time - self.time_info[0].departure_time
   
   def get_total_travel_time(self) -> float:
       """Get total travel time in minutes"""
       travel_time = 0.0
       for i in range(len(self.time_info) - 1):
           travel_time += (self.time_info[i+1].arrival_time - 
                          self.time_info[i].departure_time - 
                          self.time_info[i+1].wait_time)
       return travel_time
   
   def get_total_visit_time(self) -> float:
       """Get total visit time in minutes"""
       return sum(attr.visit_time for attr in self.attractions)
   
   def get_total_wait_time(self) -> float:
       """Get total wait time in minutes"""
       return sum(info.wait_time for info in self.time_info)
   
   def get_total_cost(self) -> float:
       """Get total cost of the route in CAD"""
       from utils import Transport, Config
       
       total_cost = sum(attr.cost for attr in self.attractions)
       
       if self.hotel and self.attractions:
           if self.transport_modes and len(self.transport_modes) > 0 and self.transport_modes[0] == TransportMode.CAR:
               travel_time = Transport.get_travel_time(
                   self.hotel.name, self.attractions[0].name, TransportMode.CAR)
               if travel_time > 0:
                   total_cost += travel_time * Config.CAR_COST_PER_MINUTE
           
           for i in range(len(self.attractions) - 1):
               if i+1 < len(self.transport_modes) and self.transport_modes[i+1] == TransportMode.CAR:
                   travel_time = Transport.get_travel_time(
                       self.attractions[i].name, self.attractions[i+1].name, TransportMode.CAR)
                   if travel_time > 0:
                       total_cost += travel_time * Config.CAR_COST_PER_MINUTE
           
           if len(self.transport_modes) > len(self.attractions):
               return_mode = self.transport_modes[len(self.attractions)]
               if return_mode == TransportMode.CAR:
                   travel_time = Transport.get_travel_time(
                       self.attractions[-1].name, self.hotel.name, TransportMode.CAR)
                   if travel_time > 0:
                       total_cost += travel_time * Config.CAR_COST_PER_MINUTE
       
       return total_cost
   
   def get_total_rating(self) -> float:
       """Get sum of attraction ratings"""
       if not self.attractions:
           return 0.0
       return sum(attr.rating for attr in self.attractions)
   
   def get_neighborhoods(self) -> Set[str]:
       """Get unique neighborhoods visited"""
       return {attr.neighborhood for attr in self.attractions}
   
   def can_add_attraction(self, attraction: Attraction, mode: TransportMode) -> Tuple[bool, float, float]:
       """
       Check if an attraction can be feasibly added to the route
       
       Args:
           attraction: The attraction to check
           mode: Transport mode for reaching this attraction from the previous location
           
       Returns:
           (is_feasible, arrival_time, departure_time)
       """
       from utils import Transport
       
       if not self.hotel:
           return False, 0, 0
       
       cache_key = (attraction.name, mode.value)
       if cache_key in self._attraction_compatibility_cache:
           return self._attraction_compatibility_cache[cache_key]
       
       if not self.attractions:
           current_time = self.start_time
           from_name = self.hotel.name
       else:
           if len(self.time_info) <= len(self.attractions):
               self.recalculate_time_info()
               if not self.time_info or len(self.time_info) <= len(self.attractions):
                   self._attraction_compatibility_cache[cache_key] = (False, 0, 0)
                   return False, 0, 0
           
           current_time = self.time_info[len(self.attractions)].departure_time
           from_name = self.attractions[-1].name
       
       travel_time = Transport.get_travel_time(from_name, attraction.name, mode)
       
       if travel_time < 0:
           self._attraction_compatibility_cache[cache_key] = (False, 0, 0)
           return False, 0, 0
       
       current_time += travel_time
       
       if not attraction.is_open_on_day(self.is_saturday):
           self._attraction_compatibility_cache[cache_key] = (False, 0, 0)
           return False, 0, 0
       
       opening_time = attraction.get_opening_time(self.is_saturday)
       closing_time = attraction.get_closing_time(self.is_saturday)
       
       if current_time < opening_time:
           current_time = opening_time
       
       arrival_time = current_time
       
       if current_time >= closing_time:
           self._attraction_compatibility_cache[cache_key] = (False, 0, 0)
           return False, 0, 0
       
       visit_end_time = current_time + attraction.visit_time
       
       if visit_end_time > closing_time:
           self._attraction_compatibility_cache[cache_key] = (False, 0, 0)
           return False, 0, 0
       
       if visit_end_time > self.end_time:
           self._attraction_compatibility_cache[cache_key] = (False, 0, 0)
           return False, 0, 0
       
       departure_time = visit_end_time
       
       result = (True, arrival_time, departure_time)
       self._attraction_compatibility_cache[cache_key] = result
       return result
   
   def add_attraction(self, attraction: Attraction, mode: TransportMode) -> bool:
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
       
       self._attraction_compatibility_cache.clear()
       
       return True
   
   def set_return_mode(self, mode: TransportMode) -> bool:
       """
       Set the transport mode for returning from the last attraction to the hotel.
       This should be called only after all attractions have been added.
       
       Args:
           mode: Transport mode for returning to hotel
           
       Returns:
           True if the mode is valid, False otherwise
       """
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
       """
       Get all valid transport modes for returning from the last attraction to the hotel

       Returns:
           List of valid transport modes in order of preference (fastest first)
       """
       from utils import Transport

       if not self.hotel or not self.attractions:
           return []

       valid_modes = []

       if len(self.time_info) <= len(self.attractions):
           self.recalculate_time_info()
           if not self.time_info or len(self.time_info) <= len(self.attractions):
               return []

       last_departure_time = self.time_info[len(self.attractions)].departure_time

       mode_times = []
       for mode in [TransportMode.WALK, TransportMode.BUS_WALK,
                  TransportMode.SUBWAY_WALK, TransportMode.CAR]:
           travel_time = Transport.get_travel_time(
               self.attractions[-1].name, self.hotel.name, mode)

           if travel_time < 0:
               continue

           if last_departure_time + travel_time <= self.end_time:
               mode_times.append((mode, travel_time))

       if not mode_times:
           return []

       valid_modes = []
       for mode, time in mode_times:
           weight = 0
           if mode == TransportMode.WALK:
               weight = 20
           elif mode == TransportMode.SUBWAY_WALK:
               weight = 40
           elif mode == TransportMode.BUS_WALK:
               weight = 30
           else:
               weight = 10

           time_factor = min(1.0, 10/time) if time > 0 else 0.1

           combined_weight = weight * time_factor

           valid_modes.append((mode, combined_weight))

       valid_modes.sort(key=lambda x: x[1], reverse=True)

       valid_modes = [mode for mode, _ in valid_modes]

       return valid_modes
   
   def recalculate_time_info(self):
       """Recalculate all time information for the route"""
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
               from_name = self.attractions[i-1].name
           
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
           
           temp_time_info[i+1] = TimeInfo(
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
           
           travel_time = Transport.get_travel_time(
               self.attractions[-1].name, self.hotel.name, mode)
           
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
       """Check if the route is valid (respects all constraints)"""
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
           
           info = self.time_info[i+1]
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
   
   def get_objectives(self) -> List[float]:
       return self.objectives
   
   def calculate_objectives(self) -> List[float]:
       """
       Calculate the objectives:
       F1: Maximize number of attractions visited
       F2: Maximize total quality (ratings)
       F3: Minimize total time
       F4: Minimize total cost
       """
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
       
       return [
           total_attractions,
           total_rating,
           total_time,
           total_cost
       ]
   
   def has_overlapping_attractions(self) -> bool:
       """Check if two daily routes have overlapping attractions"""
       day1_attractions = {attr.name for attr in self.day1_route.get_attractions()}
       
       for attr in self.day2_route.get_attractions():
           if attr.name in day1_attractions:
               return True
       
       return False
   
   def check_mandatory_attractions(self, mandatory_attractions: List[Attraction]) -> bool:
       """Check if mandatory attractions are included as first attractions of each day"""
       if mandatory_attractions and self.day1_route.get_attractions():
           if self.day1_route.get_attractions()[0] != mandatory_attractions[0]:
               return False
       
       if len(mandatory_attractions) > 1 and self.day2_route.get_attractions():
           if self.day2_route.get_attractions()[0] != mandatory_attractions[1]:
               return False
       
       return True