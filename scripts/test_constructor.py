import os
import sys
import time

# Ensure project root is on path
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from movns.constructor import MOVNSConstructor  # type: ignore
from models import Solution

PLACES_DIR = os.path.join(ROOT, 'places')
# Importante: o carregador de matrizes (Parser.load_transport_matrices)
# espera a RAIZ do projeto e ele mesmo concatena "travel-times" internamente.
BASE_DIR = ROOT
ATTRACTIONS_CSV = os.path.join(PLACES_DIR, 'attractions.csv')
HOTELS_CSV = os.path.join(PLACES_DIR, 'hotels.csv')


def main():
    print('=== Teste: MOVNSConstructor ===')
    print('Carregando dados de:', ATTRACTIONS_CSV, HOTELS_CSV)
    print('Base (raiz) em:', BASE_DIR)

    t0 = time.time()
    ctor = MOVNSConstructor(ATTRACTIONS_CSV, HOTELS_CSV, BASE_DIR)
    t1 = time.time()
    print(f'Inicialização concluída em {t1 - t0:.2f}s')

    pop_size = 20
    print(f'Gerando população inicial (size={pop_size})...')
    solutions = ctor.generate_initial_population(pop_size)
    t2 = time.time()
    print(f'População gerada em {t2 - t1:.2f}s: {len(solutions)} soluções')

    valid = 0
    invalid = 0
    for i, sol in enumerate(solutions, 1):
        try:
            # Verifica estrutura básica
            assert sol.hotel is not None
            d1 = sol.day1_route
            d2 = sol.day2_route
            ok1 = (d1 is not None and d1.is_valid() and d1.get_num_attractions() >= 0)
            ok2 = (d2 is not None and d2.is_valid() and d2.get_num_attractions() >= 0)
            # Recalcula objetivos por garantia
            obj = sol.calculate_objectives()
            assert len(obj) == 4
            valid += 1 if (ok1 and ok2) else 0
            if not (ok1 and ok2):
                invalid += 1
                print(f' - Solução {i} inválida: day1_ok={ok1}, day2_ok={ok2}')
        except Exception as e:
            invalid += 1
            print(f' - Erro na solução {i}: {e!r}')

    print(f'Resumo: válidas={valid}, inválidas={invalid}')
    if valid == 0:
        raise SystemExit('Nenhuma solução válida gerada; verifique dados/matrizes.')

    # Mostra um exemplo
    s0 = solutions[0]
    print('\nExemplo de solução:')
    print('Hotel:', s0.hotel.name)
    print('Dia 1 atrações:', [a.name for a in s0.day1_route.attractions])
    print('Dia 1 modos:', [m.name for m in s0.day1_route.transport_modes])
    print('Dia 2 atrações:', [a.name for a in s0.day2_route.attractions])
    print('Dia 2 modos:', [m.name for m in s0.day2_route.transport_modes])
    print('Objetivos:', s0.objectives or s0.calculate_objectives())


if __name__ == '__main__':
    main()
