import random
import copy
import time
from typing import List, Optional
from models import Solution
from crossover import Crossover
from mutation import Mutator

class NSGA2:
    def __init__(self, constructor, population_size=100):
        self.constructor = constructor
        self.population_size = population_size
        self.population = []
        self.crossover = Crossover(constructor)
        self.mutator = Mutator(constructor)
        self.pareto_front_sizes = []

    def initialize_population(self, mandatory_attractions=None) -> List[Solution]:
        self.population = self.constructor.generate_initial_population(self.population_size, mandatory_attractions)
        return self.population

    def run(self, generations=50, crossover_prob=0.9, mutation_prob=0.2,
            max_time: Optional[float] = None) -> List[Solution]:
        if not self.population:
            raise ValueError("Population not initialized")
        p_t = self.population
        f = self.fast_non_dominated_sort(p_t)
        self.pareto_front_sizes.append(len(f[0]))
        start_time = time.time()
        for t in range(generations):
            if max_time is not None and (time.time() - start_time) >= max_time:
                print(f"Stopping NSGA-II: time limit of {max_time}s reached at generation {t}")
                break
            q_t = []
            while len(q_t) < self.population_size:
                parent1 = self._tournament_selection(p_t, 2)
                parent2 = self._tournament_selection(p_t, 2)
                if random.random() < crossover_prob:
                    child1, child2 = self.crossover.crossover(parent1, parent2)
                else:
                    child1, child2 = copy.deepcopy(parent1), copy.deepcopy(parent2)
                if random.random() < mutation_prob:
                    child1 = self.mutator.mutate(child1)
                if random.random() < mutation_prob:
                    child2 = self.mutator.mutate(child2)
                q_t.append(child1)
                if len(q_t) < self.population_size:
                    q_t.append(child2)
            r_t = p_t + q_t
            f = self.fast_non_dominated_sort(r_t)
            p_t_plus_1 = []
            i = 0
            while len(p_t_plus_1) + len(f[i]) <= self.population_size:
                self.crowding_distance_assignment(f[i])
                for solution in f[i]:
                    p_t_plus_1.append(solution)
                i += 1
                if i >= len(f):
                    break
            if len(p_t_plus_1) < self.population_size and i < len(f):
                self.crowding_distance_assignment(f[i])
                f[i].sort(key=lambda x: x.crowding_distance, reverse=True)
                remaining = self.population_size - len(p_t_plus_1)
                for solution in f[i][:remaining]:
                    p_t_plus_1.append(solution)
            p_t = p_t_plus_1
            f = self.fast_non_dominated_sort(p_t)
            self.pareto_front_sizes.append(len(f[0]))
        self.population = p_t
        return self.population

    def fast_non_dominated_sort(self, population):
        f = [[]]
        for p in population:
            n_p = 0
            s_p = []
            for q in population:
                if p != q:
                    if self._dominates(p, q):
                        s_p.append(q)
                    elif self._dominates(q, p):
                        n_p += 1
            p.dominated_solutions = s_p
            p.domination_count = n_p
            if n_p == 0:
                p.rank = 0
                f[0].append(p)
        i = 0
        while f[i]:
            q_list = []
            for p in f[i]:
                for q in p.dominated_solutions:
                    q.domination_count -= 1
                    if q.domination_count == 0:
                        q.rank = i + 1
                        q_list.append(q)
            i += 1
            if not q_list:
                break
            f.append(q_list)
        return f

    def crowding_distance_assignment(self, front):
        l = len(front)
        if l == 0:
            return
        for solution in front:
            solution.crowding_distance = 0
        if l == 1:
            front[0].crowding_distance = float('inf')
            return
        for m in range(4):
            front.sort(key=lambda x: x.get_objectives()[m])
            front[0].crowding_distance = float('inf')
            front[l - 1].crowding_distance = float('inf')
            f_min = front[0].get_objectives()[m]
            f_max = front[l - 1].get_objectives()[m]
            if f_max == f_min:
                continue
            for i in range(1, l - 1):
                front[i].crowding_distance += (front[i + 1].get_objectives()[m] - front[i - 1].get_objectives()[m]) / (f_max - f_min)

    def _dominates(self, p, q):
        p_obj = p.get_objectives()
        q_obj = q.get_objectives()
        maximize = [True, True, False, False]
        better = False
        worse = False
        for i in range(len(p_obj)):
            if maximize[i]:
                if p_obj[i] > q_obj[i]:
                    better = True
                elif p_obj[i] < q_obj[i]:
                    worse = True
            else:
                if p_obj[i] < q_obj[i]:
                    better = True
                elif p_obj[i] > q_obj[i]:
                    worse = True
        return better and not worse

    def _tournament_selection(self, population, tournament_size=2):
        candidates = random.sample(population, tournament_size)
        best = candidates[0]
        for candidate in candidates[1:]:
            if self._crowded_comparison_operator(candidate, best):
                best = candidate
        return best

    def _crowded_comparison_operator(self, i, j):
        i_rank = getattr(i, 'rank', float('inf'))
        j_rank = getattr(j, 'rank', float('inf'))
        i_distance = getattr(i, 'crowding_distance', 0)
        j_distance = getattr(j, 'crowding_distance', 0)
        if i_rank < j_rank:
            return True
        elif i_rank == j_rank and i_distance > j_distance:
            return True
        return False
