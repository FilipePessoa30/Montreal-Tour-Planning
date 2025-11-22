import os
import sys
import time
import random
from typing import Callable, Optional, List, Tuple

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


def get_valid_base_solution(ctor: MOVNSConstructor, pop_size: int = 20) -> Solution:
    """Gera uma população e retorna a primeira solução válida encontrada."""
    sols = ctor.generate_initial_population(pop_size)
    if not sols:
        raise RuntimeError('Nenhuma solução gerada pelo construtor')

    for s in sols:
        if s.day1_route.is_valid() and s.day2_route.is_valid():
            return s
    raise RuntimeError('Nenhuma solução válida encontrada na população gerada')


def try_apply(op: Callable[[Solution], Optional[Solution]], base: Solution, attempts: int = 50) -> Tuple[Optional[Solution], int]:
    """Tenta aplicar a vizinhança até obter um vizinho ou estourar o limite."""
    for i in range(1, attempts + 1):
        res = op(base)
        if res is not None:
            return res, i
    return None, attempts


def validate_solution(sol: Solution) -> Tuple[bool, List[str]]:
    """Valida aspectos essenciais da solução gerada por uma vizinhança."""
    errs: List[str] = []

    # Função auxiliar para validar rota diária com checagens extras
    def validate_day(tag: str, route) -> None:
        # recalcula estrutura de tempo para garantir consistência
        route.recalculate_time_info()
        if not route.is_valid():
            errs.append(f'{tag} inválido')
            return
        # time_info deve ter início+fim+uma entrada por atração
        expected_ti = route.get_num_attractions() + 2
        if not route.get_time_info() or len(route.get_time_info()) != expected_ti:
            errs.append(f'{tag} time_info inconsistente (esperado {expected_ti}, obtido {len(route.get_time_info()) if route.get_time_info() else 0})')
        # quando há atrações, deve existir segmento de volta ao hotel (implicado por time_info válido)
        if route.get_num_attractions() > 0 and len(route.get_time_info()) < expected_ti:
            errs.append(f'{tag} sem retorno ao hotel')

    validate_day('day1', sol.day1_route)
    validate_day('day2', sol.day2_route)

    if sol.has_overlapping_attractions():
        errs.append('atrações repetidas entre os dias')

    # força recálculo e checa formato dos objetivos
    try:
        obj = sol.calculate_objectives()
        if not (isinstance(obj, list) and len(obj) == 4):
            errs.append('objetivos inválidos')
    except Exception as e:
        errs.append(f'erro ao calcular objetivos: {e!r}')

    return (len(errs) == 0), errs


def main():
    print('=== Teste: Operadores de Vizinhança (MOVNS) ===')
    print('Carregando dados...')
    t0 = time.time()
    ctor = MOVNSConstructor(ATTRACTIONS_CSV, HOTELS_CSV, BASE_DIR)
    t1 = time.time()
    print(f'Construtor pronto em {t1 - t0:.2f}s')

    print('Gerando solução base...')
    base = get_valid_base_solution(ctor, pop_size=30)
    print('Base:')
    print(' - Hotel:', base.hotel.name)
    print(' - Dia1:', [a.name for a in base.day1_route.attractions])
    print(' - Dia2:', [a.name for a in base.day2_route.attractions])
    print(' - Obj:', base.calculate_objectives())

    alg = MOVNS(ctor, solution_count=10, archive_max=30)

    # Mapeia nome legível -> função bound
    ops = {
        'swap_within_day': alg._neighborhood_swap_within_day,
        'move_between_days': alg._neighborhood_move_between_days,
        'replace_attraction': alg._neighborhood_replace_attraction,
        'add_attraction': alg._neighborhood_add_attraction,
        'remove_attraction': alg._neighborhood_remove_attraction,
        'change_hotel': alg._neighborhood_change_hotel,
        'change_transport': alg._neighborhood_change_transport,
    }

    print('\nAplicando vizinhanças...')
    results = []
    for name, op in ops.items():
        # Cada op faz deepcopy internamente; passamos a base original.
        neighbor, tries = try_apply(op, base, attempts=60)
        if neighbor is None:
            results.append((name, 'FAIL', f'sem vizinho após {tries} tentativas'))
            print(f' - {name}: FAIL (sem vizinho após {tries} tentativas)')
            continue

        ok, errs = validate_solution(neighbor)
        if not ok:
            results.append((name, 'FAIL', '; '.join(errs)))
            print(f' - {name}: FAIL ({"; ".join(errs)})')
            continue

        base_obj = base.calculate_objectives()
        nb_obj = neighbor.calculate_objectives()
        delta = [nb_obj[i] - base_obj[i] for i in range(4)]
        results.append((name, 'OK', f'delta={delta}'))
        print(f' - {name}: OK  Δ={delta}')

    print('\nResumo:')
    ok_count = sum(1 for _, status, _ in results if status == 'OK')
    fail_count = len(results) - ok_count
    print(f'OK={ok_count}, FAIL={fail_count} de {len(results)}')
    for name, status, msg in results:
        print(f' * {name}: {status} - {msg}')


if __name__ == '__main__':
    main()
