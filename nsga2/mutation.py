import random
import copy
from typing import List, Set
from models import Solution, DailyRoute, Attraction, TransportMode
from utils import Transport, Config

class Mutator:
    def __init__(self, constructor):
        self.constructor = constructor
        self.add_attraction_prob = 0.4
        self.remove_attraction_prob = 0.15
        self.swap_attraction_prob = 0.25
        self.move_between_days_prob = 0.2
        self.change_hotel_prob = 0.3
        self.change_transport_mode_prob = 0.4

    def mutate(self, solution: Solution) -> Solution:
        mutated = copy.deepcopy(solution)
        success = False
        if random.random() < self.change_hotel_prob:
            if self._mutate_hotel(mutated):
                success = True
        mutation_type = random.random()
        if mutation_type < self.add_attraction_prob:
            if self._add_attraction(mutated):
                success = True
        elif mutation_type < self.add_attraction_prob + self.remove_attraction_prob:
            if self._remove_attraction(mutated):
                success = True
        elif mutation_type < self.add_attraction_prob + self.remove_attraction_prob + self.swap_attraction_prob:
            if self._swap_attraction(mutated):
                success = True
        else:
            if self._move_between_days(mutated):
                success = True
        if random.random() < self.change_transport_mode_prob:
            if self._mutate_transport_mode(mutated):
                success = True
        if success:
            mutated.day1_route.recalculate_time_info()
            mutated.day2_route.recalculate_time_info()
            mutated.objectives = mutated.calculate_objectives()
            if mutated.day1_route.get_num_attractions() == 0:
                used = {attr.name for attr in mutated.day2_route.get_attractions()}
                self._ensure_day_has_attraction(mutated.day1_route, used)
            if mutated.day2_route.get_num_attractions() == 0:
                used = {attr.name for attr in mutated.day1_route.get_attractions()}
                self._ensure_day_has_attraction(mutated.day2_route, used)
            mutated.objectives = mutated.calculate_objectives()
        else:
            mutated = solution
        return mutated

    def _mutate_hotel(self, solution: Solution) -> bool:
        hotel_candidates = [h for h in self.constructor.working_hotels if h.name != solution.hotel.name]
        if not hotel_candidates:
            return False
        for _ in range(min(10, len(hotel_candidates))):
            new_hotel = random.choice(hotel_candidates)
            hotel_candidates.remove(new_hotel)
            new_day1 = copy.deepcopy(solution.day1_route)
            new_day2 = copy.deepcopy(solution.day2_route)
            new_day1.set_hotel(new_hotel)
            new_day2.set_hotel(new_hotel)
            new_day1.recalculate_time_info()
            new_day2.recalculate_time_info()
            if new_day1.is_valid() and new_day2.is_valid():
                solution.hotel = new_hotel
                solution.day1_route = new_day1
                solution.day2_route = new_day2
                return True
        return False

    def _add_attraction(self, solution: Solution) -> bool:
        day1_count = solution.day1_route.get_num_attractions()
        day2_count = solution.day2_route.get_num_attractions()
        if day1_count == 0 and day2_count > 0:
            day_route = solution.day1_route
        elif day2_count == 0 and day1_count > 0:
            day_route = solution.day2_route
        elif day1_count < day2_count:
            day_route = solution.day1_route if random.random() < 0.7 else solution.day2_route
        elif day2_count < day1_count:
            day_route = solution.day2_route if random.random() < 0.7 else solution.day1_route
        else:
            day_route = solution.day1_route if random.random() < 0.5 else solution.day2_route
        used_attractions = {attr.name for attr in solution.day1_route.get_attractions()}
        used_attractions.update(attr.name for attr in solution.day2_route.get_attractions())
        return self._add_attraction_at_end(day_route, used_attractions)

    def _add_attraction_at_end(self, day_route: DailyRoute, used_attractions: Set[str]) -> bool:
        is_saturday = day_route.is_saturday
        available = self.constructor.saturday_open_attractions if is_saturday else self.constructor.sunday_open_attractions
        candidates = [a for a in available if a.name not in used_attractions]
        random.shuffle(candidates)
        original_attractions = day_route.attractions.copy()
        original_transport_modes = day_route.transport_modes.copy()
        for attraction in candidates[:15]:
            if day_route.get_num_attractions() == 0:
                from_name = day_route.hotel.name
            else:
                from_name = day_route.attractions[-1].name
            to_modes = self._get_valid_transport_modes(from_name, attraction.name)
            if not to_modes:
                continue
            return_modes = self._get_valid_transport_modes(attraction.name, day_route.hotel.name)
            if not return_modes:
                continue
            to_mode = self._choose_preferred_transport_mode(to_modes, from_name, attraction.name)
            return_mode = self._choose_preferred_transport_mode(return_modes, attraction.name, day_route.hotel.name)
            if day_route.attractions:
                day_route.attractions.append(attraction)
                if len(day_route.transport_modes) > len(day_route.attractions) - 1:
                    day_route.transport_modes = day_route.transport_modes[:-1] + [to_mode, return_mode]
                else:
                    day_route.transport_modes.append(to_mode)
                    day_route.transport_modes.append(return_mode)
            else:
                day_route.attractions = [attraction]
                day_route.transport_modes = [to_mode, return_mode]
            day_route.recalculate_time_info()
            if day_route.is_valid():
                return True
            day_route.attractions = original_attractions.copy()
            day_route.transport_modes = original_transport_modes.copy()
        return False

    def _remove_attraction(self, solution: Solution) -> bool:
        day1_count = solution.day1_route.get_num_attractions()
        day2_count = solution.day2_route.get_num_attractions()
        if day1_count <= 1 and day2_count <= 1:
            return False
        if day1_count <= 1:
            day_route = solution.day2_route
        elif day2_count <= 1:
            day_route = solution.day1_route
        elif day1_count > day2_count:
            day_route = solution.day1_route if random.random() < 0.7 else solution.day2_route
        elif day2_count > day1_count:
            day_route = solution.day2_route if random.random() < 0.7 else solution.day1_route
        else:
            day_route = solution.day1_route if random.random() < 0.5 else solution.day2_route
        if day_route.get_num_attractions() <= 1:
            return False
        position = random.randint(0, day_route.get_num_attractions() - 1)
        original_attractions = day_route.attractions.copy()
        original_transport_modes = day_route.transport_modes.copy()
        if position == 0:
            day_route.attractions = day_route.attractions[1:]
            valid_modes = self._get_valid_transport_modes(day_route.hotel.name, day_route.attractions[0].name)
            if not valid_modes:
                day_route.attractions = original_attractions
                day_route.transport_modes = original_transport_modes
                return False
            to_mode = self._choose_preferred_transport_mode(valid_modes, day_route.hotel.name, day_route.attractions[0].name)
            day_route.transport_modes = [to_mode] + original_transport_modes[2:]
        elif position == day_route.get_num_attractions() - 1:
            day_route.attractions = day_route.attractions[:-1]
            if day_route.attractions:
                valid_modes = self._get_valid_transport_modes(day_route.attractions[-1].name, day_route.hotel.name)
                if not valid_modes:
                    day_route.attractions = original_attractions
                    day_route.transport_modes = original_transport_modes
                    return False
                return_mode = self._choose_preferred_transport_mode(valid_modes, day_route.attractions[-1].name, day_route.hotel.name)
                day_route.transport_modes = original_transport_modes[:-2] + [return_mode]
            else:
                day_route.transport_modes = []
        else:
            prev_attr = day_route.attractions[position - 1]
            next_attr = day_route.attractions[position + 1]
            valid_modes = self._get_valid_transport_modes(prev_attr.name, next_attr.name)
            if not valid_modes:
                day_route.attractions = original_attractions
                day_route.transport_modes = original_transport_modes
                return False
            new_mode = self._choose_preferred_transport_mode(valid_modes, prev_attr.name, next_attr.name)
            day_route.attractions = day_route.attractions[:position] + day_route.attractions[position + 1:]
            day_route.transport_modes = original_transport_modes[:position] + [new_mode] + original_transport_modes[position + 2:]
        day_route.recalculate_time_info()
        if day_route.is_valid():
            return True
        day_route.attractions = original_attractions
        day_route.transport_modes = original_transport_modes
        return False

    def _swap_attraction(self, solution: Solution) -> bool:
        day_route = solution.day1_route if random.random() < 0.5 else solution.day2_route
        if day_route.get_num_attractions() == 0:
            return False
        position = random.randint(0, day_route.get_num_attractions() - 1)
        used_attractions = {attr.name for attr in solution.day1_route.get_attractions()}
        used_attractions.update(attr.name for attr in solution.day2_route.get_attractions())
        current_attr = day_route.attractions[position]
        used_attractions.remove(current_attr.name)
        is_saturday = day_route.is_saturday
        available = self.constructor.saturday_open_attractions if is_saturday else self.constructor.sunday_open_attractions
        candidates = [a for a in available if a.name not in used_attractions]
        random.shuffle(candidates)
        original_attractions = day_route.attractions.copy()
        original_transport_modes = day_route.transport_modes.copy()
        for new_attr in candidates[:15]:
            if position > 0:
                prev_attr = day_route.attractions[position - 1]
                to_modes = self._get_valid_transport_modes(prev_attr.name, new_attr.name)
            else:
                to_modes = self._get_valid_transport_modes(day_route.hotel.name, new_attr.name)
            if not to_modes:
                continue
            if position < day_route.get_num_attractions() - 1:
                next_attr = day_route.attractions[position + 1]
                from_modes = self._get_valid_transport_modes(new_attr.name, next_attr.name)
            else:
                from_modes = self._get_valid_transport_modes(new_attr.name, day_route.hotel.name)
            if not from_modes:
                continue
            to_mode = self._choose_preferred_transport_mode(to_modes, day_route.hotel.name if position == 0 else day_route.attractions[position - 1].name, new_attr.name)
            from_mode = self._choose_preferred_transport_mode(from_modes, new_attr.name, day_route.hotel.name if position == day_route.get_num_attractions() - 1 else day_route.attractions[position + 1].name)
            day_route.attractions[position] = new_attr
            day_route.transport_modes[position] = to_mode
            if position < len(day_route.transport_modes) - 1:
                day_route.transport_modes[position + 1] = from_mode
            day_route.recalculate_time_info()
            if day_route.is_valid():
                return True
            day_route.attractions = original_attractions.copy()
            day_route.transport_modes = original_transport_modes.copy()
        return False

    def _move_between_days(self, solution: Solution) -> bool:
        day1_count = solution.day1_route.get_num_attractions()
        day2_count = solution.day2_route.get_num_attractions()
        if day1_count <= 1 and day2_count <= 1:
            return False
        if day1_count > day2_count:
            source_route = solution.day1_route
            target_route = solution.day2_route
        elif day2_count > day1_count:
            source_route = solution.day2_route
            target_route = solution.day1_route
        else:
            if random.random() < 0.5:
                source_route = solution.day1_route
                target_route = solution.day2_route
            else:
                source_route = solution.day2_route
                target_route = solution.day1_route
        if source_route.get_num_attractions() <= 1:
            return False
        position = random.randint(0, source_route.get_num_attractions() - 1)
        attraction = source_route.attractions[position]
        if not attraction.is_open_on_day(target_route.is_saturday):
            return False
        orig_src_attrs = source_route.attractions.copy()
        orig_src_modes = source_route.transport_modes.copy()
        orig_tgt_attrs = target_route.attractions.copy()
        orig_tgt_modes = target_route.transport_modes.copy()
        if position == 0:
            source_route.attractions = source_route.attractions[1:]
            if source_route.attractions:
                valid_modes = self._get_valid_transport_modes(source_route.hotel.name, source_route.attractions[0].name)
                if not valid_modes:
                    source_route.attractions = orig_src_attrs
                    source_route.transport_modes = orig_src_modes
                    return False
                to_mode = self._choose_preferred_transport_mode(valid_modes, source_route.hotel.name, source_route.attractions[0].name)
                source_route.transport_modes = [to_mode] + orig_src_modes[2:]
            else:
                source_route.transport_modes = []
        elif position == len(orig_src_attrs) - 1:
            source_route.attractions = source_route.attractions[:-1]
            if source_route.attractions:
                valid_modes = self._get_valid_transport_modes(source_route.attractions[-1].name, source_route.hotel.name)
                if not valid_modes:
                    source_route.attractions = orig_src_attrs
                    source_route.transport_modes = orig_src_modes
                    return False
                return_mode = self._choose_preferred_transport_mode(valid_modes, source_route.attractions[-1].name, source_route.hotel.name)
                source_route.transport_modes = orig_src_modes[:-2] + [return_mode]
            else:
                source_route.transport_modes = []
        else:
            prev_attr = source_route.attractions[position - 1]
            next_attr = source_route.attractions[position + 1]
            valid_modes = self._get_valid_transport_modes(prev_attr.name, next_attr.name)
            if not valid_modes:
                source_route.attractions = orig_src_attrs
                source_route.transport_modes = orig_src_modes
                return False
            new_mode = self._choose_preferred_transport_mode(valid_modes, prev_attr.name, next_attr.name)
            source_route.attractions = source_route.attractions[:position] + source_route.attractions[position + 1:]
            source_route.transport_modes = orig_src_modes[:position] + [new_mode] + orig_src_modes[position + 2:]
        source_route.recalculate_time_info()
        if not source_route.is_valid() and source_route.get_num_attractions() > 0:
            source_route.attractions = orig_src_attrs
            source_route.transport_modes = orig_src_modes
            source_route.recalculate_time_info()
            return False
        if target_route.get_num_attractions() == 0:
            from_name = target_route.hotel.name
        else:
            from_name = target_route.attractions[-1].name
        to_modes = self._get_valid_transport_modes(from_name, attraction.name)
        if not to_modes:
            source_route.attractions = orig_src_attrs
            source_route.transport_modes = orig_src_modes
            source_route.recalculate_time_info()
            return False
        return_modes = self._get_valid_transport_modes(attraction.name, target_route.hotel.name)
        if not return_modes:
            source_route.attractions = orig_src_attrs
            source_route.transport_modes = orig_src_modes
            source_route.recalculate_time_info()
            return False
        to_mode = self._choose_preferred_transport_mode(to_modes, from_name, attraction.name)
        return_mode = self._choose_preferred_transport_mode(return_modes, attraction.name, target_route.hotel.name)
        if target_route.attractions:
            target_route.attractions.append(attraction)
            if len(target_route.transport_modes) > len(target_route.attractions) - 1:
                target_route.transport_modes = target_route.transport_modes[:-1] + [to_mode, return_mode]
            else:
                target_route.transport_modes.append(to_mode)
                target_route.transport_modes.append(return_mode)
        else:
            target_route.attractions = [attraction]
            target_route.transport_modes = [to_mode, return_mode]
        target_route.recalculate_time_info()
        if target_route.is_valid():
            return True
        source_route.attractions = orig_src_attrs
        source_route.transport_modes = orig_src_modes
        source_route.recalculate_time_info()
        target_route.attractions = orig_tgt_attrs
        target_route.transport_modes = orig_tgt_modes
        target_route.recalculate_time_info()
        return False

    def _mutate_transport_mode(self, solution: Solution) -> bool:
        day_route = solution.day1_route if random.random() < 0.5 else solution.day2_route
        if len(day_route.transport_modes) == 0:
            return False
        segment_idx = random.randint(0, len(day_route.transport_modes) - 1)
        if segment_idx == 0:
            from_name = day_route.hotel.name
            to_name = day_route.attractions[0].name
        elif segment_idx < len(day_route.attractions):
            from_name = day_route.attractions[segment_idx - 1].name
            to_name = day_route.attractions[segment_idx].name
        else:
            from_name = day_route.attractions[-1].name
            to_name = day_route.hotel.name
        current_mode = day_route.transport_modes[segment_idx]
        valid_modes = [m for m in self._get_valid_transport_modes(from_name, to_name) if m != current_mode]
        if not valid_modes:
            return False
        original_transport_modes = day_route.transport_modes.copy()
        new_mode = self._choose_preferred_transport_mode(valid_modes, from_name, to_name)
        day_route.transport_modes[segment_idx] = new_mode
        day_route.recalculate_time_info()
        if day_route.is_valid():
            return True
        day_route.transport_modes = original_transport_modes
        return False

    def _ensure_day_has_attraction(self, day_route: DailyRoute, used_attractions: Set[str]) -> bool:
        if day_route.get_num_attractions() > 0:
            return True
        is_saturday = day_route.is_saturday
        available = self.constructor.saturday_open_attractions if is_saturday else self.constructor.sunday_open_attractions
        candidates = [a for a in available if a.name not in used_attractions]
        random.shuffle(candidates)
        for attraction in candidates[:20]:
            to_modes = self._get_valid_transport_modes(day_route.hotel.name, attraction.name)
            if not to_modes:
                continue
            from_modes = self._get_valid_transport_modes(attraction.name, day_route.hotel.name)
            if not from_modes:
                continue
            to_mode = self._choose_preferred_transport_mode(to_modes, day_route.hotel.name, attraction.name)
            return_mode = self._choose_preferred_transport_mode(from_modes, attraction.name, day_route.hotel.name)
            day_route.attractions = [attraction]
            day_route.transport_modes = [to_mode, return_mode]
            day_route.recalculate_time_info()
            if day_route.is_valid():
                return True
            day_route.attractions = []
            day_route.transport_modes = []
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
