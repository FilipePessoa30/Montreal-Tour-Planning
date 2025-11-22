import os
import sys
import time
import random
import io
from contextlib import redirect_stdout
from typing import Callable, Optional, List, Tuple, Dict

# Garante que a raiz do projeto esteja no sys.path
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from movns.constructor import MOVNSConstructor  # type: ignore
from movns.movns import MOVNS  # type: ignore
from models import Solution

PLACES_DIR = os.path.join(ROOT, 'places')
BASE_DIR = ROOT  # Parser.load_transport_matrices concatena "travel-times" internamente
ATTRACTIONS_CSV = os.path.join(PLACES_DIR, 'attractions.csv')
HOTELS_CSV = os.path.join(PLACES_DIR, 'hotels.csv')

MAX_ATTEMPTS_PER_OP = 60
SEEDS = list(range(1, 51))  # 50 seeds: 1..50
POP_SIZE = 30


def validate_solution(sol: Solution) -> Tuple[bool, List[str]]:
    errs: List[str] = []

    def validate_day(tag: str, route) -> None:
        route.recalculate_time_info()
        if not route.is_valid():
            errs.append(f'{tag} inválido')
            return
        expected_ti = route.get_num_attractions() + 2
        ti = route.get_time_info()
        if not ti or len(ti) != expected_ti:
            errs.append(f'{tag} time_info inconsistente (esperado {expected_ti}, obtido {len(ti) if ti else 0})')
        if route.get_num_attractions() > 0 and len(route.get_time_info()) < expected_ti:
            errs.append(f'{tag} sem retorno ao hotel')

    validate_day('day1', sol.day1_route)
    validate_day('day2', sol.day2_route)

    if sol.has_overlapping_attractions():
        errs.append('atrações repetidas entre os dias')

    try:
        obj = sol.calculate_objectives()
        if not (isinstance(obj, list) and len(obj) == 4):
            errs.append('objetivos inválidos')
    except Exception as e:
        errs.append(f'erro ao calcular objetivos: {e!r}')

    return (len(errs) == 0), errs


def dominates(obj_new: List[float], obj_base: List[float]) -> bool:
    # maximize F1,F2; minimize F3,F4
    maximize = [True, True, False, False]
    at_least_as_good = True
    strictly_better = False
    for i in range(4):
        a = obj_new[i]
        b = obj_base[i]
        if maximize[i]:
            if a < b:
                at_least_as_good = False
                break
            if a > b:
                strictly_better = True
        else:
            if a > b:
                at_least_as_good = False
                break
            if a < b:
                strictly_better = True
    return at_least_as_good and strictly_better


def try_apply(op: Callable[[Solution], Optional[Solution]], base: Solution, attempts: int = MAX_ATTEMPTS_PER_OP) -> Tuple[Optional[Solution], int]:
    for i in range(1, attempts + 1):
        res = op(base)
        if res is not None:
            return res, i
    return None, attempts


def generate_base_solution(ctor: MOVNSConstructor, pop_size: int) -> Solution:
    # Suprime stdout durante a geração de população para reduzir ruído
    buf = io.StringIO()
    with redirect_stdout(buf):
        sols = ctor.generate_initial_population(pop_size)
    for s in sols:
        ok, _ = validate_solution(s)
        if ok:
            return s
    # fallback: retorna a primeira mesmo inválida para diagnóstico (mas em tese não deve ocorrer)
    if sols:
        return sols[0]
    raise RuntimeError('Nenhuma solução gerada pelo construtor')


def main():
    print('=== Teste: Operadores de Vizinhança com 50 sementes ===')
    t0 = time.time()
    ctor = MOVNSConstructor(ATTRACTIONS_CSV, HOTELS_CSV, BASE_DIR)
    t1 = time.time()
    print(f'Construtor carregado uma vez em {t1 - t0:.2f}s')

    # Inicializa MOVNS uma vez apenas para obter a lista de operadores (nomes)
    alg = MOVNS(ctor, solution_count=10, archive_max=30)
    ops = {
        'swap_within_day': alg._neighborhood_swap_within_day,
        'move_between_days': alg._neighborhood_move_between_days,
        'replace_attraction': alg._neighborhood_replace_attraction,
        'add_attraction': alg._neighborhood_add_attraction,
        'remove_attraction': alg._neighborhood_remove_attraction,
        'change_hotel': alg._neighborhood_change_hotel,
        'change_transport': alg._neighborhood_change_transport,
    }

    # Estatísticas por operador
    stats: Dict[str, Dict[str, float]] = {name: {
        'seeds': 0,
        'neighbor_found': 0,
        'valid_neighbor': 0,
        'dominates': 0,
        'imp_F1': 0,  # atrações ↑
        'imp_F2': 0,  # qualidade ↑
        'imp_F3': 0,  # tempo ↓
        'imp_F4': 0   # custo ↓
    } for name in ops.keys()}

    for idx, seed in enumerate(SEEDS, 1):
        random.seed(seed)
        base = generate_base_solution(ctor, POP_SIZE)
        base_obj = base.calculate_objectives()

        # Recria o objeto MOVNS para isolar caches de modo por seed e reata as funções
        alg = MOVNS(ctor, solution_count=10, archive_max=30)
        ops = {
            'swap_within_day': alg._neighborhood_swap_within_day,
            'move_between_days': alg._neighborhood_move_between_days,
            'replace_attraction': alg._neighborhood_replace_attraction,
            'add_attraction': alg._neighborhood_add_attraction,
            'remove_attraction': alg._neighborhood_remove_attraction,
            'change_hotel': alg._neighborhood_change_hotel,
            'change_transport': alg._neighborhood_change_transport,
        }

        for name, op in ops.items():
            stats[name]['seeds'] += 1
            neighbor, _ = try_apply(op, base, attempts=MAX_ATTEMPTS_PER_OP)
            if neighbor is None:
                continue
            stats[name]['neighbor_found'] += 1

            ok, _errs = validate_solution(neighbor)
            if not ok:
                continue

            stats[name]['valid_neighbor'] += 1
            nb_obj = neighbor.calculate_objectives()

            if dominates(nb_obj, base_obj):
                stats[name]['dominates'] += 1

            # melhorias marginais por objetivo
            if nb_obj[0] > base_obj[0]:
                stats[name]['imp_F1'] += 1
            if nb_obj[1] > base_obj[1]:
                stats[name]['imp_F2'] += 1
            if nb_obj[2] < base_obj[2]:
                stats[name]['imp_F3'] += 1
            if nb_obj[3] < base_obj[3]:
                stats[name]['imp_F4'] += 1

        if idx % 10 == 0:
            print(f'... progresso: {idx}/{len(SEEDS)} seeds processadas')

    print('\nResumo por operador (sobre 50 seeds):')
    for name in ops.keys():
        s = stats[name]
        seeds = s['seeds'] or 1
        print(f'- {name}:')
        print(f'  * vizinho encontrado: {int(s["neighbor_found"])} ({s["neighbor_found"] / seeds:.0%})')
        print(f'  * vizinho válido:    {int(s["valid_neighbor"])} ({s["valid_neighbor"] / seeds:.0%})')
        print(f'  * dominou base:      {int(s["dominates"])} ({s["dominates"] / seeds:.0%})')
        print(f'  * melhorou F1/F2/F3/F4: {int(s["imp_F1"])}/{int(s["imp_F2"])}/{int(s["imp_F3"])}/{int(s["imp_F4"])})')

    t2 = time.time()
    print(f'Tempo total: {t2 - t1:.2f}s (após construir o construtor)')


if __name__ == '__main__':
    main()
