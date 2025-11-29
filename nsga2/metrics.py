import math
from typing import List

def calculate_hypervolume(solutions, reference_point: List[float]) -> float:
    if not solutions:
        return 0.0
    objectives = [s.get_objectives() for s in solutions]
    normalized = []
    for obj in objectives:
        norm = [
            (reference_point[0] - obj[0]) / reference_point[0] if reference_point[0] != 0 else 0,
            (reference_point[1] - obj[1]) / reference_point[1] if reference_point[1] != 0 else 0,
            obj[2] / reference_point[2] if reference_point[2] != 0 else 0,
            obj[3] / reference_point[3] if reference_point[3] != 0 else 0
        ]
        if all(n >= 0 and n <= 1 for n in norm):
            normalized.append(norm)
    if not normalized:
        return 0.0
    hv = 0.0
    for point in normalized:
        contribution = 1.0
        for val in point:
            contribution *= (1.0 - val)
        hv += contribution
    return hv / len(normalized)

def calculate_igd(solutions, reference_front: List[List[float]]) -> float:
    if not solutions or not reference_front:
        return float('inf')
    objectives = [s.get_objectives() for s in solutions]
    total_distance = 0.0
    for ref_point in reference_front:
        min_distance = float('inf')
        for obj in objectives:
            distance = 0.0
            for i in range(len(ref_point)):
                distance += (ref_point[i] - obj[i]) ** 2
            distance = math.sqrt(distance)
            if distance < min_distance:
                min_distance = distance
        total_distance += min_distance
    return total_distance / len(reference_front)

def calculate_spread(solutions) -> float:
    if len(solutions) < 2:
        return 1.0
    objectives = [s.get_objectives() for s in solutions]
    num_objectives = len(objectives[0])
    total_spread = 0.0
    for m in range(num_objectives):
        values = sorted([obj[m] for obj in objectives])
        if len(values) < 2:
            continue
        f_min = values[0]
        f_max = values[-1]
        if f_max == f_min:
            continue
        distances = []
        for i in range(len(values) - 1):
            distances.append(values[i + 1] - values[i])
        if not distances:
            continue
        mean_distance = sum(distances) / len(distances)
        if mean_distance == 0:
            continue
        d_f = abs(values[0] - f_min)
        d_l = abs(values[-1] - f_max)
        sum_diff = sum(abs(d - mean_distance) for d in distances)
        spread_m = (d_f + d_l + sum_diff) / (d_f + d_l + len(distances) * mean_distance)
        total_spread += spread_m
    return total_spread / num_objectives if num_objectives > 0 else 1.0

def get_pareto_front(solutions) -> List:
    if not solutions:
        return []
    front = []
    for p in solutions:
        is_dominated = False
        for q in solutions:
            if p != q and dominates(q, p):
                is_dominated = True
                break
        if not is_dominated:
            front.append(p)
    return front

def dominates(p, q) -> bool:
    p_obj = p.get_objectives()
    q_obj = q.get_objectives()
    maximize = [True, True, False, False]
    better = False
    for i in range(len(p_obj)):
        if maximize[i]:
            if p_obj[i] > q_obj[i]:
                better = True
            elif p_obj[i] < q_obj[i]:
                return False
        else:
            if p_obj[i] < q_obj[i]:
                better = True
            elif p_obj[i] > q_obj[i]:
                return False
    return better

def print_metrics(solutions, reference_point=None):
    if reference_point is None:
        reference_point = [20.0, 100.0, 1500.0, 1000.0]
    pareto_front = get_pareto_front(solutions)
    reference_front = [s.get_objectives() for s in pareto_front]
    hv = calculate_hypervolume(solutions, reference_point)
    igd = calculate_igd(solutions, reference_front)
    spread = calculate_spread(solutions)
    print(f"\nMetrics:")
    print(f"  Pareto front size: {len(pareto_front)}")
    print(f"  Hypervolume: {hv:.4f}")
    print(f"  IGD: {igd:.4f}")
    print(f"  Spread: {spread:.4f}")
    return {"hypervolume": hv, "igd": igd, "spread": spread, "pareto_size": len(pareto_front)}
