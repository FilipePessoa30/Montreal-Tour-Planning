import os
import sys
import time
import random
import io
from contextlib import redirect_stdout
from typing import Dict, List, Tuple, Optional

# Garantir raiz no path
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from movns.constructor import MOVNSConstructor  # type: ignore
from movns.movns import MOVNS  # type: ignore
from models import Solution, DailyRoute, TransportMode, TimeInfo, LocationType  # type: ignore
from utils import Transport  # type: ignore

PLACES_DIR = os.path.join(ROOT, 'places')
BASE_DIR = ROOT
ATTRACTIONS_CSV = os.path.join(PLACES_DIR, 'attractions.csv')
HOTELS_CSV = os.path.join(PLACES_DIR, 'hotels.csv')

SEEDS = list(range(1, 51))
POP_SIZE = 30
MAX_ATTEMPTS_PER_OP = 60


def generate_base_solution(ctor: MOVNSConstructor, pop_size: int) -> Solution:
    buf = io.StringIO()
    with redirect_stdout(buf):
        sols = ctor.generate_initial_population(pop_size)
    for s in sols:
        if s.day1_route.is_valid() and s.day2_route.is_valid() and not s.has_overlapping_attractions():
            return s
    if sols:
        return sols[0]
    raise RuntimeError('Nenhuma solução gerada pelo construtor')


def check_day_constraints(route: DailyRoute) -> Dict[str, Tuple[bool, Optional[str]]]:
    checks: Dict[str, Tuple[bool, Optional[str]]] = {}

    # Recalcula time_info antes
    route.recalculate_time_info()

    # C1: hotel atribuído
    checks['hotel_assigned'] = (route.hotel is not None, None if route.hotel else 'hotel None')

    # C2: validade geral do modelo
    checks['route_is_valid'] = (route.is_valid(), None if route.is_valid() else 'is_valid=False')

    n = route.get_num_attractions()
    ti = route.get_time_info()

    # C3: estrutura do time_info
    if n == 0:
        # Sem atrações, time_info pode ser vazio, e rota válida deve ser True
        checks['time_info_length'] = ((ti is None or len(ti) == 0), f'time_info len={len(ti) if ti else 0} (esperado 0)')
    else:
        exp = n + 2
        checks['time_info_length'] = (ti is not None and len(ti) == exp, f'time_info len={len(ti) if ti else 0}, esperado {exp}')

    # C4: primeiro e último elementos do time_info
    if n > 0 and ti and len(ti) == n + 2:
        checks['time_info_first_hotel'] = (ti[0].location_type == LocationType.HOTEL, f'primeiro={ti[0].location_type}')
        checks['time_info_last_hotel'] = (ti[-1].location_type == LocationType.HOTEL, f'ultimo={ti[-1].location_type}')
    else:
        checks['time_info_first_hotel'] = (n == 0 or (ti and ti[0].location_type == LocationType.HOTEL), None)
        checks['time_info_last_hotel'] = (n == 0 or (ti and len(ti) == n + 2 and ti[-1].location_type == LocationType.HOTEL), None)

    # C5: coerência temporal e esperas não negativas
    ok_monotonic = True
    msg_mono = ''
    ok_wait = True
    msg_wait = ''
    if ti and len(ti) >= 1:
        prev_dep = ti[0].departure_time
        for idx in range(1, len(ti)):
            arr = ti[idx].arrival_time
            wt = ti[idx].wait_time
            dep = ti[idx].departure_time
            if wt < 0:
                ok_wait = False
                msg_wait = f'wait negativo em idx={idx}: {wt}'
                break
            if not (arr >= prev_dep):
                ok_monotonic = False
                msg_mono = f'arrive<{prev_dep} em idx={idx}: {arr}'
                break
            if not (dep >= arr):
                ok_monotonic = False
                msg_mono = f'dep<{arr} em idx={idx}: {dep}'
                break
            prev_dep = dep
    checks['time_monotonic'] = (ok_monotonic, msg_mono if not ok_monotonic else None)
    checks['wait_non_negative'] = (ok_wait, msg_wait if not ok_wait else None)

    # C6: janelas de abertura
    ok_open = True
    msg_open = ''
    if n > 0 and ti and len(ti) == n + 2:
        for i, attr in enumerate(route.get_attractions()):
            info = ti[i + 1]
            is_sat = route.is_saturday
            opening = attr.get_opening_time(is_sat)
            closing = attr.get_closing_time(is_sat)
            if info.arrival_time < opening or info.arrival_time >= closing or info.departure_time > closing:
                ok_open = False
                msg_open = f'{attr.name}: arr={info.arrival_time}, dep={info.departure_time}, win=[{opening},{closing}]'
                break
    checks['opening_windows_respected'] = (ok_open, msg_open if not ok_open else None)

    # C7: finaliza antes das 20:00
    if n > 0 and ti and len(ti) == n + 2:
        checks['return_before_end'] = (ti[-1].arrival_time <= route.end_time, f'arrival_end={ti[-1].arrival_time} > {route.end_time}')
    else:
        checks['return_before_end'] = (True, None)

    # C8: modos e tempos de deslocamento válidos
    ok_modes = True
    msg_modes = ''
    modes = route.get_transport_modes()
    if n > 0 and modes and len(modes) >= 1:
        # segmentos: hotel->a0, a0->a1, ..., a_{n-1}->hotel
        for seg in range(len(modes)):
            if seg == 0:
                frm = route.hotel.name
                to = route.get_attractions()[0].name if n > 0 else route.hotel.name
            elif seg < n:
                frm = route.get_attractions()[seg - 1].name
                to = route.get_attractions()[seg].name
            else:
                frm = route.get_attractions()[-1].name
                to = route.hotel.name
            mm = modes[seg]
            t = Transport.get_travel_time(frm, to, mm)
            if t < 0:
                ok_modes = False
                msg_modes = f'seg={seg} {frm}->{to} modo={mm} tempo={t}'
                break
    checks['segment_modes_valid'] = (ok_modes, msg_modes if not ok_modes else None)

    # C9: existência de retorno quando há atrações
    if n > 0:
        checks['has_return_segment'] = (len(route.get_transport_modes()) > n, f'len(modes)={len(route.get_transport_modes())} n={n}')
    else:
        checks['has_return_segment'] = (True, None)

    return checks


def check_solution_constraints(sol: Solution) -> Dict[str, Tuple[bool, Optional[str]]]:
    results: Dict[str, Tuple[bool, Optional[str]]] = {}

    # Solução: hotel presente
    results['solution_hotel_assigned'] = (sol.hotel is not None, None if sol.hotel else 'hotel None')

    # Sem duplicidade entre dias
    no_overlap = not sol.has_overlapping_attractions()
    results['no_duplicate_across_days'] = (no_overlap, None if no_overlap else 'duplicatas entre dias')

    # Restrições por dia (prefixos day1_, day2_)
    d1 = check_day_constraints(sol.day1_route)
    for k, v in d1.items():
        results[f'day1_{k}'] = v
    d2 = check_day_constraints(sol.day2_route)
    for k, v in d2.items():
        results[f'day2_{k}'] = v

    return results


def main():
    print('=== Teste de Restrições (50 seeds) ===')
    t0 = time.time()
    ctor = MOVNSConstructor(ATTRACTIONS_CSV, HOTELS_CSV, BASE_DIR)
    t1 = time.time()
    print(f'Construtor pronto em {t1 - t0:.2f}s')

    # Referência às vizinhanças
    alg0 = MOVNS(ctor, solution_count=10, archive_max=30)
    op_names = [
        'swap_within_day',
        'move_between_days',
        'replace_attraction',
        'add_attraction',
        'remove_attraction',
        'change_hotel',
        'change_transport',
    ]

    # Estatísticas: por restrição e por operador
    # Estrutura: stats[operator][constraint] = {'checks': X, 'passes': Y}
    stats: Dict[str, Dict[str, Dict[str, int]]] = {name: {} for name in op_names}

    def update_stats(op: str, results: Dict[str, Tuple[bool, Optional[str]]]) -> None:
        if op not in stats:
            stats[op] = {}
        for cname, (ok, _msg) in results.items():
            if cname not in stats[op]:
                stats[op][cname] = {'checks': 0, 'passes': 0}
            stats[op][cname]['checks'] += 1
            if ok:
                stats[op][cname]['passes'] += 1

    for idx, seed in enumerate(SEEDS, 1):
        random.seed(seed)
        base = generate_base_solution(ctor, POP_SIZE)

        # Valida a própria base (como operador 'base')
        base_results = check_solution_constraints(base)
        update_stats('base', base_results)

        # Para cada seed, re-instancia o MOVNS para isolar caches e obter funções bound
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
            # Tenta obter um vizinho
            neighbor: Optional[Solution] = None
            for _ in range(MAX_ATTEMPTS_PER_OP):
                neighbor = op(base)
                if neighbor is not None:
                    break
            if neighbor is None:
                # Mesmo sem vizinho, ainda contamos que a checagem foi tentada (mas sem resultados)
                continue

            # Checa restrições do vizinho
            res = check_solution_constraints(neighbor)
            update_stats(name, res)

        if idx % 10 == 0:
            print(f'... {idx}/{len(SEEDS)} seeds processadas')

    # Relatório final
    print('\nResumo de Restrições (percentual de passagens):')
    # Inclui também a base
    all_ops = ['base'] + op_names

    # Coleta conjunto total de constraints vistas
    all_constraints: List[str] = []
    for op in all_ops:
        if op in stats:
            for cname in stats[op].keys():
                if cname not in all_constraints:
                    all_constraints.append(cname)

    for op in all_ops:
        if op not in stats:
            continue
        print(f'\n- {op}:')
        for cname in sorted(all_constraints):
            data = stats[op].get(cname)
            if not data or data['checks'] == 0:
                print(f'  * {cname}: n/a')
                continue
            pct = (data['passes'] / data['checks']) * 100.0
            print(f'  * {cname}: {pct:.0f}% ({data["passes"]}/{data["checks"]})')

    t2 = time.time()
    print(f"Tempo total: {t2 - t1:.2f}s")


if __name__ == '__main__':
    main()
