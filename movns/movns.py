
import random
import time
import copy
from typing import List, Dict, Tuple, Set, Optional, Any
from models import Solution, Hotel, DailyRoute, Attraction, TransportMode

class MOVNS:
    """
    Multi-Objective Variable Neighborhood Search implementation for tourist route optimization.
    Similar to NSGA-II, this algorithm aims to find a Pareto-optimal front of solutions
    that balance multiple competing objectives:
    
    F1: Maximize number of attractions visited
    F2: Maximize total quality (ratings)
    F3: Minimize total time (travel time)
    F4: Minimize total cost
    
    Unlike NSGA-II, MOVNS uses a systematic neighborhood exploration strategy
    with multiple neighborhood structures of increasing size.
    """
    
    def __init__(self, constructor, solution_count=100, archive_max=30):
        self.constructor = constructor
        self.pareto_set = []
        self.solution_count = solution_count
        self.archive_max = archive_max
        
        self.neighborhoods = [
            self._neighborhood_swap_within_day,
            self._neighborhood_move_between_days,
            self._neighborhood_replace_attraction,
            self._neighborhood_add_attraction,
            self._neighborhood_remove_attraction,
            self._neighborhood_change_hotel,
            self._neighborhood_change_transport
        ]
        
        self.iteration_metrics = []
        self.best_solutions = {}
        
        self._mode_validity_cache = {}
    
    def initialize_population(self) -> List[Solution]:
        print(f"Generating initial population of size {self.solution_count}...")
        
        initial_solutions = self.constructor.generate_initial_population(self.solution_count)
        
        if initial_solutions:
            self._calculate_initial_metrics(initial_solutions)
        
        for solution in initial_solutions:
            self._add_to_pareto_set(solution)
        
        print(f"Initial Pareto set size: {len(self.pareto_set)}")
        return self.pareto_set
    
    def run(self, max_iterations=100, max_no_improvement=20) -> List[Solution]:
        if not self.pareto_set:
            raise ValueError("Pareto set not initialized. Call initialize_population first.")
        
        print(f"Starting MOVNS optimization ({max_iterations} max iterations)...")
        
        iteration = 0
        no_improvement = 0
        
        pareto_sizes = [len(self.pareto_set)]
        
        while iteration < max_iterations and no_improvement < max_no_improvement:
            start_time = time.time()
            current_size = len(self.pareto_set)
            improved = False
            
            for i, solution in enumerate(self.pareto_set[:]):
                k = 0
                
                while k < len(self.neighborhoods):
                    new_solution = self._shake(solution, k)
                    
                    if new_solution:
                        improved_solution = self._multi_objective_local_search(new_solution)
                        
                        if self._add_to_pareto_set(improved_solution):
                            improved = True
                            k = 0
                        else:
                            k += 1
                    else:
                        k += 1
            
            if improved or len(self.pareto_set) > current_size:
                no_improvement = 0
            else:
                no_improvement += 1
            
            iteration += 1
            elapsed = time.time() - start_time
            pareto_sizes.append(len(self.pareto_set))
            
            metrics = self._calculate_iteration_metrics(iteration, elapsed)
            self.iteration_metrics.append(metrics)
            
            print(f"Iteration {iteration}/{max_iterations} | "
                  f"Pareto set size: {len(self.pareto_set)} | "
                  f"No improvement: {no_improvement}/{max_no_improvement} | "
                  f"Time: {elapsed:.2f}s")
        
        if iteration >= max_iterations:
            print(f"Stopping: maximum iterations ({max_iterations}) reached")
        else:
            print(f"Stopping: {max_no_improvement} iterations without improvement")
        
        print(f"Final Pareto set size: {len(self.pareto_set)}")
        
        return self.pareto_set
    
    def _shake(self, solution: Solution, k: int) -> Optional[Solution]:
        perturbed = copy.deepcopy(solution)
        
        if k < len(self.neighborhoods):
            return self.neighborhoods[k](perturbed)
        else:
            return None
    
    def _multi_objective_local_search(self, solution: Solution) -> Solution:
        improved = copy.deepcopy(solution)
        
        weights = [random.random() for _ in range(4)]
        total = sum(weights)
        weights = [w / total for w in weights]
        
        maximize = [True, True, False, False]
        
        improved = self._weighted_local_search(improved, weights, maximize)
        
        return improved
    
    def _weighted_local_search(self, solution: Solution, weights: List[float], 
                             maximize: List[bool]) -> Solution:
        current = copy.deepcopy(solution)
        best = copy.deepcopy(solution)
        
        best_value = self._calculate_weighted_value(best.get_objectives(), weights, maximize)
        
        improved = True
        while improved:
            improved = False
            
            for neighborhood in self.neighborhoods:
                neighbor = neighborhood(current)
                
                if neighbor:
                    neighbor_value = self._calculate_weighted_value(
                        neighbor.get_objectives(), weights, maximize)
                    
                    if neighbor_value > best_value:
                        best = copy.deepcopy(neighbor)
                        best_value = neighbor_value
                        improved = True
            
            if improved:
                current = copy.deepcopy(best)
        
        return best
    
    def _calculate_weighted_value(self, objectives: List[float], 
                                weights: List[float], maximize: List[bool]) -> float:
        value = 0.0
        
        for i in range(len(objectives)):
            obj_value = objectives[i] if maximize[i] else -objectives[i]
            value += weights[i] * obj_value
        
        return value
    
    def _add_to_pareto_set(self, solution: Solution) -> bool:
        if not solution:
            return False
        
        solution.objectives = solution.calculate_objectives()
        
        for existing in self.pareto_set:
            if self._dominates(existing, solution):
                return False
        
        dominated = []
        for existing in self.pareto_set:
            if self._dominates(solution, existing):
                dominated.append(existing)
        
        for dominated_solution in dominated:
            self.pareto_set.remove(dominated_solution)
        
        self.pareto_set.append(solution)
        
        if len(self.pareto_set) > self.archive_max:
            self._truncate_archive()
        
        return True or len(dominated) > 0
    
    def _truncate_archive(self):
        while len(self.pareto_set) > self.archive_max:
            crowding_distances = self._calculate_crowding_distances()
            
            min_distance = float('inf')
            min_index = -1
            for i, distance in enumerate(crowding_distances):
                if distance < min_distance:
                    min_distance = distance
                    min_index = i
            
            if min_index >= 0:
                self.pareto_set.pop(min_index)
            else:
                self.pareto_set.pop(random.randint(0, len(self.pareto_set) - 1))
    
    def _calculate_crowding_distances(self) -> List[float]:
        n = len(self.pareto_set)
        if n <= 2:
            return [float('inf')] * n
        
        distances = [0.0] * n
        
        for obj_idx in range(4):
            sorted_indices = sorted(range(n), 
                                  key=lambda i: self.pareto_set[i].objectives[obj_idx])
            
            distances[sorted_indices[0]] = float('inf')
            distances[sorted_indices[-1]] = float('inf')
            
            obj_range = (self.pareto_set[sorted_indices[-1]].objectives[obj_idx] - 
                        self.pareto_set[sorted_indices[0]].objectives[obj_idx])
            
            if obj_range > 0:
                for i in range(1, n - 1):
                    idx = sorted_indices[i]
                    prev_idx = sorted_indices[i - 1]
                    next_idx = sorted_indices[i + 1]
                    
                    distance = (self.pareto_set[next_idx].objectives[obj_idx] - 
                              self.pareto_set[prev_idx].objectives[obj_idx]) / obj_range
                    
                    distances[idx] += distance
        
        return distances
    
    def _dominates(self, solution1: Solution, solution2: Solution) -> bool:
        obj1 = solution1.get_objectives()
        obj2 = solution2.get_objectives()
        
        maximize = [True, True, False, False]
        
        at_least_as_good = True
        for i in range(len(obj1)):
            if maximize[i]:
                if obj1[i] < obj2[i]:
                    at_least_as_good = False
                    break
            else:
                if obj1[i] > obj2[i]:
                    at_least_as_good = False
                    break
        
        if not at_least_as_good:
            return False
        
        strictly_better = False
        for i in range(len(obj1)):
            if maximize[i]:
                if obj1[i] > obj2[i]:
                    strictly_better = True
                    break
            else:
                if obj1[i] < obj2[i]:
                    strictly_better = True
                    break
        
        return strictly_better
    
    def _neighborhood_swap_within_day(self, solution: Solution) -> Optional[Solution]:
        day_route = solution.day1_route if random.random() < 0.5 else solution.day2_route
        
        if day_route.get_num_attractions() < 2:
            return None
        
        positions = random.sample(range(day_route.get_num_attractions()), 2)
        pos1, pos2 = positions
        
        modified = copy.deepcopy(solution)
        modified_route = modified.day1_route if day_route is solution.day1_route else modified.day2_route
        
        original_attractions = modified_route.attractions.copy()
        original_modes = modified_route.transport_modes.copy()
        
        modified_route.attractions[pos1], modified_route.attractions[pos2] = \
            modified_route.attractions[pos2], modified_route.attractions[pos1]
        
        self._update_transport_modes(modified_route)
        
        self._update_route_timing(modified_route)
        
        if modified_route.is_valid():
            modified.objectives = modified.calculate_objectives()
            return modified
        
        return None
    
    def _neighborhood_move_between_days(self, solution: Solution) -> Optional[Solution]:
        modified = copy.deepcopy(solution)
        
        if modified.day1_route.get_num_attractions() == 0:
            if modified.day2_route.get_num_attractions() == 0:
                return None
            source_route = modified.day2_route
            target_route = modified.day1_route
        elif modified.day2_route.get_num_attractions() == 0:
            source_route = modified.day1_route
            target_route = modified.day2_route
        else:
            if random.random() < 0.5:
                source_route = modified.day1_route
                target_route = modified.day2_route
            else:
                source_route = modified.day2_route
                target_route = modified.day1_route
        
        if source_route.get_num_attractions() == 0:
            return None
        
        pos = random.randint(0, source_route.get_num_attractions() - 1)
        attraction = source_route.attractions[pos]
        
        is_saturday = target_route.is_saturday
        if not attraction.is_open_on_day(is_saturday):
            return None
        
        source_original = source_route.attractions.copy()
        source_modes = source_route.transport_modes.copy()
        target_original = target_route.attractions.copy()
        target_modes = target_route.transport_modes.copy()
        
        source_route.attractions.pop(pos)
        
        target_route.attractions.append(attraction)
        
        self._update_transport_modes(source_route)
        self._update_transport_modes(target_route)
        
        self._update_route_timing(source_route)
        self._update_route_timing(target_route)
        
        if source_route.is_valid() and target_route.is_valid():
            modified.objectives = modified.calculate_objectives()
            return modified
        
        source_route.attractions = source_original
        source_route.transport_modes = source_modes
        target_route.attractions = target_original
        target_route.transport_modes = target_modes
        
        self._update_route_timing(source_route)
        self._update_route_timing(target_route)
        
        return None
    
    def _neighborhood_replace_attraction(self, solution: Solution) -> Optional[Solution]:
        modified = copy.deepcopy(solution)
        
        if modified.day1_route.get_num_attractions() == 0 and modified.day2_route.get_num_attractions() == 0:
            return None
        
        if modified.day1_route.get_num_attractions() == 0:
            day_route = modified.day2_route
        elif modified.day2_route.get_num_attractions() == 0:
            day_route = modified.day1_route
        else:
            day_route = modified.day1_route if random.random() < 0.5 else modified.day2_route
        
        if day_route.get_num_attractions() == 0:
            return None
        
        pos = random.randint(0, day_route.get_num_attractions() - 1)
        
        used_attractions = set()
        for attr in modified.day1_route.get_attractions():
            used_attractions.add(attr.name)
        for attr in modified.day2_route.get_attractions():
            used_attractions.add(attr.name)
        
        is_saturday = day_route.is_saturday
        available_attractions = (self.constructor.saturday_open_attractions if is_saturday 
                               else self.constructor.sunday_open_attractions)
        
        available_attractions = [attr for attr in available_attractions 
                               if attr.name not in used_attractions]
        
        if not available_attractions:
            return None
        
        original_attraction = day_route.attractions[pos]
        original_attractions = day_route.attractions.copy()
        original_modes = day_route.transport_modes.copy()
        
        for _ in range(min(10, len(available_attractions))):
            new_attraction = random.choice(available_attractions)
            available_attractions.remove(new_attraction)
            
            day_route.attractions[pos] = new_attraction
            
            self._update_transport_modes(day_route)
            
            self._update_route_timing(day_route)
            
            if day_route.is_valid():
                modified.objectives = modified.calculate_objectives()
                return modified
        
        day_route.attractions[pos] = original_attraction
        day_route.attractions = original_attractions
        day_route.transport_modes = original_modes
        self._update_route_timing(day_route)
        
        return None
    
    def _neighborhood_add_attraction(self, solution: Solution) -> Optional[Solution]:
        modified = copy.deepcopy(solution)
        
        day1_count = modified.day1_route.get_num_attractions()
        day2_count = modified.day2_route.get_num_attractions()
        
        if day1_count < day2_count:
            day_route = modified.day1_route
        elif day2_count < day1_count:
            day_route = modified.day2_route
        else:
            day_route = modified.day1_route if random.random() < 0.5 else modified.day2_route
        
        used_attractions = set()
        for attr in modified.day1_route.get_attractions():
            used_attractions.add(attr.name)
        for attr in modified.day2_route.get_attractions():
            used_attractions.add(attr.name)
        
        is_saturday = day_route.is_saturday
        available_attractions = (self.constructor.saturday_open_attractions if is_saturday 
                               else self.constructor.sunday_open_attractions)
        
        available_attractions = [attr for attr in available_attractions 
                               if attr.name not in used_attractions]
        
        if not available_attractions:
            return None
        
        original_attractions = day_route.attractions.copy()
        original_modes = day_route.transport_modes.copy()
        
        max_pos = day_route.get_num_attractions()
        pos = random.randint(0, max_pos)
        
        for _ in range(min(10, len(available_attractions))):
            new_attraction = random.choice(available_attractions)
            available_attractions.remove(new_attraction)
            
            day_route.attractions.insert(pos, new_attraction)
            
            self._update_transport_modes(day_route)
            
            self._update_route_timing(day_route)
            
            if day_route.is_valid():
                modified.objectives = modified.calculate_objectives()
                return modified
            
            day_route.attractions = original_attractions.copy()
        
        day_route.attractions = original_attractions
        day_route.transport_modes = original_modes
        self._update_route_timing(day_route)
        
        return None
    
    def _neighborhood_remove_attraction(self, solution: Solution) -> Optional[Solution]:
        modified = copy.deepcopy(solution)
        
        day1_count = modified.day1_route.get_num_attractions()
        day2_count = modified.day2_route.get_num_attractions()
        
        if day1_count == 0 and day2_count == 0:
            return None
        
        if day1_count == 0:
            day_route = modified.day2_route
        elif day2_count == 0:
            day_route = modified.day1_route
        elif day1_count > day2_count:
            day_route = modified.day1_route
        elif day2_count > day1_count:
            day_route = modified.day2_route
        else:
            day_route = modified.day1_route if random.random() < 0.5 else modified.day2_route
        
        if day_route.get_num_attractions() <= 1:
            return None
        
        original_attractions = day_route.attractions.copy()
        original_modes = day_route.transport_modes.copy()
        
        pos = random.randint(0, day_route.get_num_attractions() - 1)
        
        day_route.attractions.pop(pos)
        
        self._update_transport_modes(day_route)
        
        self._update_route_timing(day_route)
        
        if day_route.is_valid():
            modified.objectives = modified.calculate_objectives()
            return modified
        
        day_route.attractions = original_attractions
        day_route.transport_modes = original_modes
        self._update_route_timing(day_route)
        
        return None
    
    def _neighborhood_change_hotel(self, solution: Solution) -> Optional[Solution]:
        modified = copy.deepcopy(solution)
        
        candidates = [hotel for hotel in self.constructor.working_hotels 
                     if hotel.name != modified.hotel.name]
        
        if not candidates:
            return None
        
        original_hotel = modified.hotel
        original_day1 = copy.deepcopy(modified.day1_route)
        original_day2 = copy.deepcopy(modified.day2_route)
        
        for _ in range(min(10, len(candidates))):
            new_hotel = random.choice(candidates)
            candidates.remove(new_hotel)
            
            modified.hotel = new_hotel
            modified.day1_route.set_hotel(new_hotel)
            modified.day2_route.set_hotel(new_hotel)
            
            self._update_transport_modes(modified.day1_route)
            self._update_transport_modes(modified.day2_route)
            
            self._update_route_timing(modified.day1_route)
            self._update_route_timing(modified.day2_route)
            
            if modified.day1_route.is_valid() and modified.day2_route.is_valid():
                modified.objectives = modified.calculate_objectives()
                return modified
        
        modified.hotel = original_hotel
        modified.day1_route = original_day1
        modified.day2_route = original_day2
        
        return None
    
    def _neighborhood_change_transport(self, solution: Solution) -> Optional[Solution]:
        modified = copy.deepcopy(solution)
        
        day_route = modified.day1_route if random.random() < 0.5 else modified.day2_route
        
        if len(day_route.transport_modes) == 0:
            return None
        
        segment_idx = random.randint(0, len(day_route.transport_modes) - 1)
        
        current_mode = day_route.transport_modes[segment_idx]
        
        if segment_idx == 0:
            from_name = modified.hotel.name
            to_name = day_route.attractions[0].name if day_route.attractions else modified.hotel.name
        elif segment_idx < len(day_route.attractions):
            from_name = day_route.attractions[segment_idx - 1].name
            to_name = day_route.attractions[segment_idx].name
        else:
            from_name = day_route.attractions[-1].name
            to_name = modified.hotel.name
        
        all_modes = [TransportMode.WALK, TransportMode.BUS_WALK, 
                    TransportMode.SUBWAY_WALK, TransportMode.CAR]
        
        if current_mode in all_modes:
            all_modes.remove(current_mode)
        
        valid_modes = []
        for mode in all_modes:
            travel_time = self._get_travel_time(from_name, to_name, mode)
            if travel_time >= 0:
                valid_modes.append(mode)
        
        if not valid_modes:
            return None
        
        new_mode = random.choice(valid_modes)
        
        original_modes = day_route.transport_modes.copy()
        
        day_route.transport_modes[segment_idx] = new_mode
        
        self._update_route_timing(day_route)
        
        if day_route.is_valid():
            modified.objectives = modified.calculate_objectives()
            return modified
        
        day_route.transport_modes = original_modes
        self._update_route_timing(day_route)
        
        return None
    
    def _update_transport_modes(self, day_route: DailyRoute) -> None:
        day_route.transport_modes = []
        
        if not day_route.attractions:
            return
        
        first_attr = day_route.attractions[0]
        valid_modes = self._get_valid_transport_modes(day_route.hotel.name, first_attr.name)
        if valid_modes:
            mode = self._choose_preferred_mode(valid_modes)
            day_route.transport_modes.append(mode)
        else:
            day_route.transport_modes.append(TransportMode.CAR)
        
        for i in range(len(day_route.attractions) - 1):
            from_attr = day_route.attractions[i]
            to_attr = day_route.attractions[i+1]
            valid_modes = self._get_valid_transport_modes(from_attr.name, to_attr.name)
            if valid_modes:
                mode = self._choose_preferred_mode(valid_modes)
                day_route.transport_modes.append(mode)
            else:
                day_route.transport_modes.append(TransportMode.CAR)
        
        last_attr = day_route.attractions[-1]
        valid_modes = self._get_valid_transport_modes(last_attr.name, day_route.hotel.name)
        if valid_modes:
            mode = self._choose_preferred_mode(valid_modes)
            day_route.transport_modes.append(mode)
        else:
            day_route.transport_modes.append(TransportMode.CAR)
    
    def _update_route_timing(self, day_route: DailyRoute) -> None:
        day_route.time_info = []
        
        day_route.recalculate_time_info()
    
    def _get_valid_transport_modes(self, from_name: str, to_name: str) -> List[TransportMode]:
        cache_key = (from_name, to_name)
        if cache_key in self._mode_validity_cache:
            return self._mode_validity_cache[cache_key]
        
        valid_modes = []
        for mode in [TransportMode.WALK, TransportMode.BUS_WALK, 
                    TransportMode.SUBWAY_WALK, TransportMode.CAR]:
            travel_time = self._get_travel_time(from_name, to_name, mode)
            if travel_time >= 0:
                valid_modes.append(mode)
        
        self._mode_validity_cache[cache_key] = valid_modes
        return valid_modes
    
    def _get_travel_time(self, from_name: str, to_name: str, mode: TransportMode) -> float:
        from utils import Transport
        return Transport.get_travel_time(from_name, to_name, mode)
    
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
    
    def _calculate_initial_metrics(self, solutions: List[Solution]) -> Dict:
        metrics = {
            "min_attractions": float('inf'),
            "max_attractions": 0,
            "avg_attractions": 0,
            "min_quality": float('inf'),
            "max_quality": 0,
            "avg_quality": 0,
            "min_time": float('inf'),
            "max_time": 0,
            "avg_time": 0,
            "min_cost": float('inf'),
            "max_cost": 0,
            "avg_cost": 0
        }
        
        total_attractions = 0
        total_quality = 0
        total_time = 0
        total_cost = 0
        
        for solution in solutions:
            objectives = solution.get_objectives()
            
            attractions = objectives[0]
            metrics["min_attractions"] = min(metrics["min_attractions"], attractions)
            metrics["max_attractions"] = max(metrics["max_attractions"], attractions)
            total_attractions += attractions
            
            quality = objectives[1]
            metrics["min_quality"] = min(metrics["min_quality"], quality)
            metrics["max_quality"] = max(metrics["max_quality"], quality)
            total_quality += quality
            
            time_val = objectives[2]
            metrics["min_time"] = min(metrics["min_time"], time_val)
            metrics["max_time"] = max(metrics["max_time"], time_val)
            total_time += time_val
            
            cost = objectives[3]
            metrics["min_cost"] = min(metrics["min_cost"], cost)
            metrics["max_cost"] = max(metrics["max_cost"], cost)
            total_cost += cost
            
            self._update_best_solutions(solution)
        
        if solutions:
            count = len(solutions)
            metrics["avg_attractions"] = total_attractions / count
            metrics["avg_quality"] = total_quality / count
            metrics["avg_time"] = total_time / count
            metrics["avg_cost"] = total_cost / count
        
        return metrics
    
    def _calculate_iteration_metrics(self, iteration: int, elapsed_time: float) -> Dict:
        metrics = {
            "iteration": iteration,
            "elapsed_time": elapsed_time,
            "pareto_size": len(self.pareto_set),
            "min_attractions": float('inf'),
            "max_attractions": 0,
            "avg_attractions": 0,
            "min_quality": float('inf'),
            "max_quality": 0,
            "avg_quality": 0,
            "min_time": float('inf'),
            "max_time": 0,
            "avg_time": 0,
            "min_cost": float('inf'),
            "max_cost": 0,
            "avg_cost": 0
        }
        
        total_attractions = 0
        total_quality = 0
        total_time = 0
        total_cost = 0
        
        for solution in self.pareto_set:
            objectives = solution.get_objectives()
            
            attractions = objectives[0]
            metrics["min_attractions"] = min(metrics["min_attractions"], attractions)
            metrics["max_attractions"] = max(metrics["max_attractions"], attractions)
            total_attractions += attractions
            
            quality = objectives[1]
            metrics["min_quality"] = min(metrics["min_quality"], quality)
            metrics["max_quality"] = max(metrics["max_quality"], quality)
            total_quality += quality
            
            time_val = objectives[2]
            metrics["min_time"] = min(metrics["min_time"], time_val)
            metrics["max_time"] = max(metrics["max_time"], time_val)
            total_time += time_val
            
            cost = objectives[3]
            metrics["min_cost"] = min(metrics["min_cost"], cost)
            metrics["max_cost"] = max(metrics["max_cost"], cost)
            total_cost += cost
            
            self._update_best_solutions(solution)
        
        if self.pareto_set:
            count = len(self.pareto_set)
            metrics["avg_attractions"] = total_attractions / count
            metrics["avg_quality"] = total_quality / count
            metrics["avg_time"] = total_time / count
            metrics["avg_cost"] = total_cost / count
        
        return metrics
    
    def _update_best_solutions(self, solution: Solution) -> None:
        objectives = solution.get_objectives()
        
        if "attractions" not in self.best_solutions or \
           objectives[0] > self.best_solutions["attractions"].get_objectives()[0]:
            self.best_solutions["attractions"] = copy.deepcopy(solution)
        
        if "quality" not in self.best_solutions or \
           objectives[1] > self.best_solutions["quality"].get_objectives()[1]:
            self.best_solutions["quality"] = copy.deepcopy(solution)
        
        if "time" not in self.best_solutions or \
           objectives[2] < self.best_solutions["time"].get_objectives()[2]:
            self.best_solutions["time"] = copy.deepcopy(solution)
        
        if "cost" not in self.best_solutions or \
           objectives[3] < self.best_solutions["cost"].get_objectives()[3]:
            self.best_solutions["cost"] = copy.deepcopy(solution)
    
    def export_results(self, pareto_file: str, metrics_file: str) -> bool:
        try:
            import os
            pareto_dir = os.path.dirname(pareto_file)
            metrics_dir = os.path.dirname(metrics_file)
            
            if pareto_dir and not os.path.exists(pareto_dir):
                os.makedirs(pareto_dir)
            
            if metrics_dir and not os.path.exists(metrics_dir):
                os.makedirs(metrics_dir)
            
            sorted_pareto = sorted(self.pareto_set, key=lambda s: s.get_objectives()[0], reverse=True)
            
            with open(pareto_file, 'w', newline='', encoding='utf-8') as file:
                file.write("Solution;Hotel;HotelRating;HotelPrice;TotalAttractions;TotalQuality;TotalTime;TotalCost;"
                          "Day1Attractions;Day1Neighborhoods;Day1Time;Day1Cost;Day2Attractions;Day2Neighborhoods;"
                          "Day2Time;Day2Cost;Day1Sequence;Day1TransportModes;Day2Sequence;Day2TransportModes\n")
                
                for i, solution in enumerate(sorted_pareto):
                    try:
                        solution.objectives = solution.calculate_objectives()
                        
                        hotel = solution.hotel
                        day1 = solution.day1_route
                        day2 = solution.day2_route
                        objectives = solution.get_objectives()
                        
                        day1_modes = []
                        day1_attractions = day1.get_attractions()
                        day1_transport_modes = day1.get_transport_modes()
                        
                        for j in range(len(day1_transport_modes)):
                            day1_modes.append(TransportMode.get_mode_string(day1_transport_modes[j]))
                        
                        day2_modes = []
                        day2_attractions = day2.get_attractions()
                        day2_transport_modes = day2.get_transport_modes()
                        
                        for j in range(len(day2_transport_modes)):
                            day2_modes.append(TransportMode.get_mode_string(day2_transport_modes[j]))
                        
                        file.write(f"{i + 1};")
                        file.write(f"{hotel.name};")
                        file.write(f"{hotel.rating:.1f};")
                        file.write(f"{hotel.price:.2f};")
                        file.write(f"{objectives[0]:.0f};")
                        file.write(f"{objectives[1]:.1f};")
                        file.write(f"{objectives[2]:.1f};")
                        file.write(f"{objectives[3]:.2f};")
                        
                        file.write(f"{day1.get_num_attractions()};")
                        file.write(f"{len(day1.get_neighborhoods())};")
                        file.write(f"{day1.get_total_time():.1f};")
                        file.write(f"{day1.get_total_cost():.2f};")
                        
                        file.write(f"{day2.get_num_attractions()};")
                        file.write(f"{len(day2.get_neighborhoods())};")
                        file.write(f"{day2.get_total_time():.1f};")
                        file.write(f"{day2.get_total_cost():.2f};")
                        
                        file.write("|".join(attr.name for attr in day1.get_attractions()) + ";")
                        file.write("|".join(day1_modes) + ";")
                        file.write("|".join(attr.name for attr in day2.get_attractions()) + ";")
                        file.write("|".join(day2_modes) + "\n")
                    except Exception as e:
                        print(f"Error exporting solution {i+1}: {str(e)}")
                        continue
            
            with open(metrics_file, 'w', newline='', encoding='utf-8') as file:
                file.write("Iteration;ParetoSize;Time;MinAttr;MaxAttr;AvgAttr;MinQuality;"
                          "MaxQuality;AvgQuality;MinTime;MaxTime;AvgTime;MinCost;MaxCost;AvgCost\n")
                
                for metrics in self.iteration_metrics:
                    file.write(f"{metrics['iteration']};")
                    file.write(f"{metrics['pareto_size']};")
                    file.write(f"{metrics['elapsed_time']:.2f};")
                    file.write(f"{metrics['min_attractions']:.0f};")
                    file.write(f"{metrics['max_attractions']:.0f};")
                    file.write(f"{metrics['avg_attractions']:.2f};")
                    file.write(f"{metrics['min_quality']:.1f};")
                    file.write(f"{metrics['max_quality']:.1f};")
                    file.write(f"{metrics['avg_quality']:.2f};")
                    file.write(f"{metrics['min_time']:.1f};")
                    file.write(f"{metrics['max_time']:.1f};")
                    file.write(f"{metrics['avg_time']:.2f};")
                    file.write(f"{metrics['min_cost']:.2f};")
                    file.write(f"{metrics['max_cost']:.2f};")
                    file.write(f"{metrics['avg_cost']:.2f}\n")
            
            print(f"Results exported to {pareto_file} and {metrics_file}")
            return True
        except Exception as e:
            print(f"Error exporting results: {str(e)}")
            import traceback
            traceback.print_exc()
            return False