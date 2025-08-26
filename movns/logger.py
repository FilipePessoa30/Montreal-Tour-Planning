
import os
import time
import csv
from typing import List, Dict, Any, Optional
import numpy as np

class MOVNSLogger:
    """
    Logger for MOVNS algorithm to track performance metrics and detailed iteration data
    """
    
    def __init__(self, output_dir: str = "results"):
        self.output_dir = output_dir
        self.execution_log = []
        self.detailed_solutions = []
        self.start_time = time.time()
        
        os.makedirs(output_dir, exist_ok=True)
    
    def log_iteration(self, iteration: int, archive_size: int, hypervolume: float, 
                     spread: float, epsilon: Optional[float], objectives_stats: Dict[str, Any],
                     k_value: int, idle_iterations: int) -> None:
        exec_time = time.time() - self.start_time
        
        log_entry = {
            'iteration': iteration,
            'time': exec_time,
            'archive_size': archive_size,
            'hypervolume': hypervolume,
            'spread': spread,
            'epsilon': epsilon if epsilon is not None else "NA",
            'min_attractions': objectives_stats['min_attractions'],
            'avg_attractions': objectives_stats['avg_attractions'],
            'max_attractions': objectives_stats['max_attractions'],
            'min_quality': objectives_stats['min_quality'],
            'avg_quality': objectives_stats['avg_quality'],
            'max_quality': objectives_stats['max_quality'],
            'min_time': objectives_stats['min_time'],
            'avg_time': objectives_stats['avg_time'],
            'max_time': objectives_stats['max_time'],
            'min_cost': objectives_stats['min_cost'],
            'avg_cost': objectives_stats['avg_cost'],
            'max_cost': objectives_stats['max_cost'],
            'k_value': k_value,
            'idle_count': idle_iterations
        }
        
        self.execution_log.append(log_entry)
    
    def log_solution(self, solution_id: int, solution) -> None:
        objectives = solution.get_objectives()
        
        if solution.day1_route:
            day1_attractions = solution.day1_route.get_attractions()
            for i, attraction in enumerate(day1_attractions):
                start_time, end_time = self._format_time_info(solution.day1_route, i)
                if i < len(solution.day1_route.transport_modes):
                    transport_mode = solution.day1_route.transport_modes[i]
                else:
                    transport_mode = None
                
                self.detailed_solutions.append({
                    'solution_id': solution_id,
                    'day': 'Saturday',
                    'order': i + 1,
                    'poi': attraction.name,
                    'start_time': start_time,
                    'end_time': end_time,
                    'transport': transport_mode.name if transport_mode else 'WALK',
                    'duration': attraction.visit_time,
                    'cost': attraction.cost,
                    'rating': attraction.rating,
                    'hotel': solution.hotel.name,
                    'f1': objectives[0],
                    'f2': objectives[1],
                    'f3': objectives[2],
                    'f4': objectives[3]
                })
        
        if solution.day2_route:
            day2_attractions = solution.day2_route.get_attractions()
            for i, attraction in enumerate(day2_attractions):
                start_time, end_time = self._format_time_info(solution.day2_route, i)
                if i < len(solution.day2_route.transport_modes):
                    transport_mode = solution.day2_route.transport_modes[i]
                else:
                    transport_mode = None
                
                self.detailed_solutions.append({
                    'solution_id': solution_id,
                    'day': 'Sunday',
                    'order': i + 1,
                    'poi': attraction.name,
                    'start_time': start_time,
                    'end_time': end_time,
                    'transport': transport_mode.name if transport_mode else 'WALK',
                    'duration': attraction.visit_time,
                    'cost': attraction.cost,
                    'rating': attraction.rating,
                    'hotel': solution.hotel.name,
                    'f1': objectives[0],
                    'f2': objectives[1],
                    'f3': objectives[2],
                    'f4': objectives[3]
                })
    
    def _format_time_info(self, day_route, attraction_index: int) -> tuple:
        if not day_route.time_info or attraction_index >= len(day_route.time_info):
            return ("", "")

        time_info = day_route.time_info[attraction_index+1]

        start_time = self._minutes_to_hhmm(time_info.arrival_time)

        end_time = self._minutes_to_hhmm(time_info.departure_time)

        return (start_time, end_time)

    def _minutes_to_hhmm(self, minutes):
        if minutes is None:
            return ""

        hours = int(minutes // 60)
        mins = int(minutes % 60)
        return f"{hours:02d}:{mins:02d}"
    
    def save_execution_log(self) -> None:
        if not self.execution_log:
            return
        
        file_path = os.path.join(self.output_dir, "movns_execution_log.csv")
        
        try:
            with open(file_path, 'w', newline='') as csvfile:
                fieldnames = list(self.execution_log[0].keys())
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
                
                writer.writeheader()
                writer.writerows(self.execution_log)
                
            print(f"Saved {len(self.execution_log)} rows to {file_path}")
        except Exception as e:
            print(f"Error saving execution log: {str(e)}")
    
    def save_solution_routes(self, solutions: List[Any]) -> None:
        if not solutions:
            return
        
        self.detailed_solutions = []
        
        for i, solution in enumerate(solutions):
            self.log_solution(i + 1, solution)
        
        file_path = os.path.join(self.output_dir, "route_solution.csv")
        
        try:
            with open(file_path, 'w', newline='') as csvfile:
                fieldnames = list(self.detailed_solutions[0].keys())
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
                
                writer.writeheader()
                writer.writerows(self.detailed_solutions)
                
            print(f"Saved {len(self.detailed_solutions)} rows to {file_path}")
        except Exception as e:
            print(f"Error saving solution routes: {str(e)}")
    
    def elapsed_time(self) -> float:
        return time.time() - self.start_time