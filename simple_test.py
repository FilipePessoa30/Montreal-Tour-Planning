#!/usr/bin/env python3
"""
Teste simples para identificar problemas específicos
"""
import sys
import traceback

def test_imports():
    print("=== Teste de Importações ===")
    
    try:
        print("Importando models...")
        from models import Hotel, Attraction, DailyRoute, TransportMode, Solution
        print("✓ models importado com sucesso")
        
        print("Importando utils...")
        from utils import Parser, Transport, Config
        print("✓ utils importado com sucesso")
        
        print("Importando movns.constructor...")
        from movns.constructor import MOVNSConstructor
        print("✓ movns.constructor importado com sucesso")
        
        print("Importando movns.movns...")
        from movns.movns import MOVNS
        print("✓ movns.movns importado com sucesso")
        
        return True
    except Exception as e:
        print(f"✗ Erro na importação: {e}")
        traceback.print_exc()
        return False

def test_data_loading():
    print("\n=== Teste de Carregamento de Dados ===")
    
    try:
        from utils import Parser
        
        print("Carregando atrações...")
        attractions = Parser.load_attractions("places/attractions.csv")
        print(f"✓ {len(attractions)} atrações carregadas")
        
        print("Carregando hotéis...")
        hotels = Parser.load_hotels("places/hotels.csv")
        print(f"✓ {len(hotels)} hotéis carregados")
        
        print("Carregando matrizes de transporte...")
        matrices_loaded = Parser.load_transport_matrices(".")
        print(f"✓ Matrizes carregadas: {matrices_loaded}")
        
        return True
    except Exception as e:
        print(f"✗ Erro no carregamento: {e}")
        traceback.print_exc()
        return False

def test_minimal_constructor():
    print("\n=== Teste do Construtor Mínimo ===")
    
    try:
        from movns.constructor import MOVNSConstructor
        
        print("Criando construtor...")
        constructor = MOVNSConstructor(
            "places/attractions.csv",
            "places/hotels.csv", 
            "."
        )
        print("✓ Construtor criado")
        
        print("Testando geração de 1 solução...")
        solutions = constructor.generate_initial_population(1)
        print(f"✓ {len(solutions)} soluções geradas")
        
        return True
    except Exception as e:
        print(f"✗ Erro no construtor: {e}")
        traceback.print_exc()
        return False

def main():
    print("Teste Simples de Diagnóstico\n")
    
    tests = [
        ("Importações", test_imports),
        ("Carregamento de Dados", test_data_loading),
        ("Construtor Mínimo", test_minimal_constructor)
    ]
    
    for name, test_func in tests:
        print(f"Executando teste: {name}")
        success = test_func()
        if not success:
            print(f"\n✗ Teste '{name}' falhou. Parando aqui.")
            return
        print(f"✓ Teste '{name}' passou\n")
    
    print("✓ Todos os testes passaram!")

if __name__ == "__main__":
    main()
