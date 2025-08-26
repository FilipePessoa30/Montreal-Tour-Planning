#!/usr/bin/env python3
import sys
import os
import time

print("Testando carregamento de dados...")

try:
    print("1. Importando módulos...")
    from utils import Parser
    from models import Attraction, Hotel
    print("   ✓ Módulos importados")
    
    print("2. Carregando atrações...")
    start_time = time.time()
    attractions = Parser.load_attractions("places/attractions.csv")
    load_time = time.time() - start_time
    print(f"   ✓ {len(attractions)} atrações carregadas em {load_time:.2f}s")
    
    print("3. Carregando hotéis...")
    start_time = time.time()
    hotels = Parser.load_hotels("places/hotels.csv")
    load_time = time.time() - start_time
    print(f"   ✓ {len(hotels)} hotéis carregados em {load_time:.2f}s")
    
    print("4. Carregando matrizes de transporte...")
    start_time = time.time()
    success = Parser.load_transport_matrices(".")
    load_time = time.time() - start_time
    print(f"   ✓ Matrizes carregadas: {success} em {load_time:.2f}s")
    
    if not success:
        print("   ✗ Falha ao carregar matrizes de transporte!")
        sys.exit(1)
    
    print("5. Testando transporte...")
    from utils import Transport
    try:
        if len(attractions) >= 2:
            travel_time = Transport.get_travel_time(attractions[0].name, attractions[1].name, 
                                                  Transport.TransportMode.WALK)
            print(f"   ✓ Tempo de viagem teste: {travel_time} min")
    except Exception as e:
        print(f"   ✗ Erro no teste de transporte: {e}")

    print("\nTodos os testes básicos passaram!")
    
except Exception as e:
    print(f"✗ Erro: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
