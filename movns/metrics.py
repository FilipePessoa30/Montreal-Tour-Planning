
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
import copy
import random
import time
from functools import cmp_to_key

class MultiObjectiveMetrics:
    
    @staticmethod
    def normalize_objectives(solutions: List[Any], 
                           objective_indices: List[int], 
                           maximize: List[bool],
                           reference_point: Optional[List[float]] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        objectives = np.array([
            [solution.get_objectives()[idx] for idx in objective_indices]
            for solution in solutions
        ])
        
        if len(objectives) == 0:
            return np.array([]), np.array([]), np.array([])
        
        min_values = np.min(objectives, axis=0)
        max_values = np.max(objectives, axis=0)
        
        if reference_point is not None:
            ref_point = np.array([reference_point[idx] for idx in objective_indices])
            for i in range(len(objective_indices)):
                if maximize[i]:
                    min_values[i] = min(min_values[i], ref_point[i])
                else:
                    max_values[i] = max(max_values[i], ref_point[i])
        
        ranges = max_values - min_values
        
        for i in range(len(ranges)):
            if ranges[i] == 0:
                ranges[i] = 1.0
        
        normalized = np.zeros_like(objectives, dtype=float)
        for i in range(len(solutions)):
            for j in range(len(objective_indices)):
                if maximize[j]:
                    normalized[i, j] = (objectives[i, j] - min_values[j]) / ranges[j]
                else:
                    normalized[i, j] = 1 - (objectives[i, j] - min_values[j]) / ranges[j]
        
        return normalized, min_values, max_values
    
    _hypervolume_cache = {}
    _cache_hits = 0
    _cache_misses = 0
    _last_cache_clear = time.time()

    @staticmethod
    def calculate_hypervolume(solutions: List[Any],
                            objective_indices: List[int] = [0, 1, 2, 3],
                            maximize: List[bool] = [True, True, False, False],
                            reference_point: Optional[List[float]] = None) -> float:
        if not solutions:
            return 0.0

        current_time = time.time()
        if current_time - MultiObjectiveMetrics._last_cache_clear > 300:
            MultiObjectiveMetrics._hypervolume_cache.clear()
            MultiObjectiveMetrics._last_cache_clear = current_time
            MultiObjectiveMetrics._cache_hits = 0
            MultiObjectiveMetrics._cache_misses = 0

        objectives_tuples = []
        for solution in solutions:
            objectives = solution.get_objectives()
            selected_objectives = tuple(objectives[idx] for idx in objective_indices)
            objectives_tuples.append(selected_objectives)

        objectives_tuples.sort()
        cache_key = (
            tuple(objectives_tuples),
            tuple(objective_indices),
            tuple(maximize),
            tuple(reference_point) if reference_point is not None else None
        )

        if cache_key in MultiObjectiveMetrics._hypervolume_cache:
            MultiObjectiveMetrics._cache_hits += 1
            return MultiObjectiveMetrics._hypervolume_cache[cache_key]

        MultiObjectiveMetrics._cache_misses += 1

        if len(solutions) > 20 and len(objective_indices) > 3:
            sampled_solutions = MultiObjectiveMetrics._sample_representative_solutions(
                solutions, objective_indices, maximize, max_size=20
            )
            normalized, _, _ = MultiObjectiveMetrics.normalize_objectives(
                sampled_solutions, objective_indices, maximize, reference_point
            )
        else:
            normalized, _, _ = MultiObjectiveMetrics.normalize_objectives(
                solutions, objective_indices, maximize, reference_point
            )

        if normalized.size == 0:
            return 0.0

        ref_point = np.zeros(len(objective_indices))

        hypervolume = MultiObjectiveMetrics._hypervolume_exact(normalized, ref_point)

        MultiObjectiveMetrics._hypervolume_cache[cache_key] = hypervolume

        return hypervolume

    @staticmethod
    def _sample_representative_solutions(solutions: List[Any],
                                       objective_indices: List[int],
                                       maximize: List[bool],
                                       max_size: int = 20) -> List[Any]:
        if len(solutions) <= max_size:
            return solutions

        objectives = np.array([
            [solution.get_objectives()[idx] for idx in objective_indices]
            for solution in solutions
        ])

        sampled_indices = set()

        for i, obj_index in enumerate(objective_indices):
            if maximize[i]:
                best_idx = np.argmax(objectives[:, i])
                worst_idx = np.argmin(objectives[:, i])
            else:
                best_idx = np.argmin(objectives[:, i])
                worst_idx = np.argmax(objectives[:, i])

            sampled_indices.add(best_idx)
            sampled_indices.add(worst_idx)

        remaining_indices = list(set(range(len(solutions))) - sampled_indices)
        if len(remaining_indices) > max_size - len(sampled_indices):
            random_indices = random.sample(remaining_indices, max_size - len(sampled_indices))
            sampled_indices.update(random_indices)
        else:
            sampled_indices.update(remaining_indices)

        return [solutions[i] for i in sampled_indices]
    
    @staticmethod
    def _hypervolume_exact(points: np.ndarray, reference_point: np.ndarray) -> float:
        if len(points) == 0:
            return 0.0

        valid_points = []
        for point in points:
            if np.all(point >= reference_point) and np.any(point > reference_point):
                valid_points.append(point)

        if not valid_points:
            return 0.0001

        points = np.array(valid_points)

        if len(points) == 1:
            return np.prod(np.abs(points[0] - reference_point))

        if points.shape[1] == 2:
            sorted_points = points[points[:, 0].argsort()[::-1]]

            hv = 0.0
            prev_x = sorted_points[0, 0]
            prev_y = reference_point[1]

            for point in sorted_points:
                x, y = point
                if y > prev_y:
                    hv += (prev_x - reference_point[0]) * (y - prev_y)
                    prev_y = y

                prev_x = min(prev_x, x)

            if prev_x > reference_point[0]:
                hv += (prev_x - reference_point[0]) * (1.0 - prev_y)

            return max(0.0001, hv)

        if points.shape[1] == 3:
            if points.shape[0] <= 10:
                return max(0.0001, MultiObjectiveMetrics._hypervolume_recursive(
                    points, reference_point, points.shape[1] - 1))

            sorted_indices = np.argsort(points[:, 2])[::-1]
            sorted_points = points[sorted_indices]

            hv = 0.0
            prev_z = reference_point[2]

            z_values = np.unique(sorted_points[:, 2])

            if len(z_values) == 1:
                z = z_values[0]
                if z > reference_point[2]:
                    slice_area = MultiObjectiveMetrics._hypervolume_exact(
                        sorted_points[:, 0:2], reference_point[0:2])
                    hv = slice_area * (z - reference_point[2])
            else:
                slice_area = 0.0
                last_processed_idx = -1

                for z in z_values:
                    if z <= reference_point[2]:
                        continue

                    z_level_indices = np.where(sorted_points[:, 2] >= z)[0]
                    max_idx = np.max(z_level_indices)

                    if max_idx > last_processed_idx:
                        slice_points = sorted_points[:max_idx+1, 0:2]
                        slice_area = MultiObjectiveMetrics._hypervolume_exact(
                            slice_points, reference_point[0:2])
                        last_processed_idx = max_idx

                    if z > prev_z:
                        hv += slice_area * (z - prev_z)
                        prev_z = z

            return max(0.0001, hv)

        if points.shape[1] >= 4:
            return max(0.0001, MultiObjectiveMetrics._hypervolume_monte_carlo(
                points, reference_point, samples=10000))

        return max(0.0001, MultiObjectiveMetrics._hypervolume_recursive(
            points, reference_point, points.shape[1] - 1))
    
    @staticmethod
    def _hypervolume_monte_carlo(points: np.ndarray, reference_point: np.ndarray, samples: int = 20000) -> float:
        ndim = points.shape[1]
        npoints = points.shape[0]

        max_values = np.max(points, axis=0)

        total_volume = np.prod(max_values - reference_point)

        if total_volume <= 0:
            return 0.0001

        if npoints == 1:
            return np.prod(points[0] - reference_point)

        adaptive_samples = min(30000, samples * (1 + int(npoints/10)))

        chunk_size = min(5000, adaptive_samples)
        dominated_count = 0

        for i in range(0, adaptive_samples, chunk_size):
            current_chunk_size = min(chunk_size, adaptive_samples - i)
            chunk_samples = np.random.uniform(
                low=reference_point,
                high=max_values,
                size=(current_chunk_size, ndim)
            )

            for sample in chunk_samples:
                is_dominated = False

                point_batch_size = 50
                for j in range(0, npoints, point_batch_size):
                    end_idx = min(j + point_batch_size, npoints)
                    current_points = points[j:end_idx]

                    dominance = np.all(current_points >= sample, axis=1)

                    if np.any(dominance):
                        is_dominated = True
                        break

                if is_dominated:
                    dominated_count += 1

        dominated_fraction = dominated_count / adaptive_samples
        hypervolume = dominated_fraction * total_volume

        if adaptive_samples < 10000:
            correction = 0.005 * total_volume
            hypervolume = min(total_volume, hypervolume + correction)

        return max(0.0001, hypervolume)

    @staticmethod
    def _hypervolume_recursive(points: np.ndarray,
                             reference_point: np.ndarray,
                             dimension: int) -> float:
        if dimension == 0:
            if len(points) == 0:
                return 0.0
            return np.max(points[:, 0] - reference_point[0])

        sorted_indices = np.argsort(points[:, dimension])[::-1]
        sorted_points = points[sorted_indices]

        hv = 0.0
        prev_h = reference_point[dimension]

        for i in range(len(sorted_points)):
            h = sorted_points[i, dimension]
            if h > prev_h:
                dominated = []
                for j in range(i + 1):
                    if all(sorted_points[j, :dimension] >= reference_point[:dimension]):
                        dominated.append(sorted_points[j, :dimension])

                hv += (h - prev_h) * MultiObjectiveMetrics._hypervolume_recursive(
                    np.array(dominated) if dominated else np.empty((0, dimension)),
                    reference_point[:dimension],
                    dimension - 1
                )

                prev_h = h

        return max(0.0001, hv)
    
    @staticmethod
    def calculate_hypervolume_contribution(solutions: List[Any], 
                                         solution_index: int,
                                         objective_indices: List[int] = [0, 1, 2, 3],
                                         maximize: List[bool] = [True, True, False, False],
                                         reference_point: Optional[List[float]] = None) -> float:
        if not solutions or solution_index < 0 or solution_index >= len(solutions):
            return 0.0
        
        total_hv = MultiObjectiveMetrics.calculate_hypervolume(
            solutions, objective_indices, maximize, reference_point)
        
        reduced_solutions = [solutions[i] for i in range(len(solutions)) if i != solution_index]
        
        reduced_hv = MultiObjectiveMetrics.calculate_hypervolume(
            reduced_solutions, objective_indices, maximize, reference_point)
        
        return max(0.0, total_hv - reduced_hv)
    
    @staticmethod
    def calculate_spread_indicator(solutions: List[Any],
                                 objective_indices: List[int] = [0, 1, 2, 3],
                                 maximize: List[bool] = [True, True, False, False]) -> float:
        if len(solutions) < 2:
            return 0.0
        
        normalized, _, _ = MultiObjectiveMetrics.normalize_objectives(
            solutions, objective_indices, maximize)
        
        
        centroid = np.mean(normalized, axis=0)
        
        distances_from_centroid = np.sqrt(np.sum((normalized - centroid) ** 2, axis=1))
        sorted_indices = np.argsort(distances_from_centroid)
        sorted_points = normalized[sorted_indices]
        
        distances = np.sqrt(np.sum((sorted_points[1:] - sorted_points[:-1]) ** 2, axis=1))
        
        mean_distance = np.mean(distances) if len(distances) > 0 else 0.0
        
        extreme_distances = []
        for i in range(len(objective_indices)):
            min_idx = np.argmin(normalized[:, i])
            max_idx = np.argmax(normalized[:, i])
            
            min_dists = np.sqrt(np.sum((normalized - normalized[min_idx]) ** 2, axis=1))
            min_dists[min_idx] = float('inf')
            extreme_distances.append(np.min(min_dists))
            
            max_dists = np.sqrt(np.sum((normalized - normalized[max_idx]) ** 2, axis=1))
            max_dists[max_idx] = float('inf')
            extreme_distances.append(np.min(max_dists))
        
        df = np.sum(extreme_distances)
        di_sum = np.sum(np.abs(distances - mean_distance))
        
        denominator = df + (len(solutions) - 1) * mean_distance
        if denominator == 0:
            return 0.0
        
        spread = (df + di_sum) / denominator
        return spread
    
    @staticmethod
    def calculate_epsilon_indicator(solutions1: List[Any],
                                  solutions2: List[Any],
                                  objective_indices: List[int] = [0, 1, 2, 3],
                                  maximize: List[bool] = [True, True, False, False]) -> float:
        if not solutions1 or not solutions2:
            return 0.0

        objectives1 = np.array([
            [solution.get_objectives()[idx] for idx in objective_indices]
            for solution in solutions1
        ])

        objectives2 = np.array([
            [solution.get_objectives()[idx] for idx in objective_indices]
            for solution in solutions2
        ])

        if np.array_equal(objectives1, objectives2):
            return 0.0

        min_vals = np.min(np.vstack([objectives1, objectives2]), axis=0)
        max_vals = np.max(np.vstack([objectives1, objectives2]), axis=0)

        ranges = max_vals - min_vals
        ranges[ranges == 0] = 1.0

        norm_obj1 = np.zeros_like(objectives1, dtype=float)
        norm_obj2 = np.zeros_like(objectives2, dtype=float)

        for i in range(len(objective_indices)):
            if maximize[i]:
                norm_obj1[:, i] = (objectives1[:, i] - min_vals[i]) / ranges[i]
                norm_obj2[:, i] = (objectives2[:, i] - min_vals[i]) / ranges[i]
            else:
                norm_obj1[:, i] = 1.0 - (objectives1[:, i] - min_vals[i]) / ranges[i]
                norm_obj2[:, i] = 1.0 - (objectives2[:, i] - min_vals[i]) / ranges[i]

        epsilon_values = []

        for sol2 in norm_obj2:
            min_epsilon = float('inf')

            for sol1 in norm_obj1:
                diffs = sol2 - sol1
                max_diff = np.max(diffs)
                min_epsilon = min(min_epsilon, max_diff)

            epsilon_values.append(min_epsilon)

        epsilon = max(epsilon_values) if epsilon_values else 0.0

        return min(1.0, max(-1.0, epsilon))
    
    @staticmethod
    def hypervolume_truncate(solutions: List[Any], 
                           max_size: int,
                           objective_indices: List[int] = [0, 1, 2, 3],
                           maximize: List[bool] = [True, True, False, False]) -> List[Any]:
        if len(solutions) <= max_size:
            return solutions
        
        truncated = solutions.copy()
        
        while len(truncated) > max_size:
            min_contribution = float('inf')
            min_index = -1
            
            for i in range(len(truncated)):
                contribution = MultiObjectiveMetrics.calculate_hypervolume_contribution(
                    truncated, i, objective_indices, maximize)
                
                if contribution < min_contribution:
                    min_contribution = contribution
                    min_index = i
            
            if min_index >= 0:
                truncated.pop(min_index)
            else:
                truncated.pop(random.randint(0, len(truncated) - 1))
        
        return truncated