#!/usr/bin/env python3
"""
Script de debug para identificar problemas no código
"""

import os
import sys

def test_basic_imports():
    """Teste básico de importações"""
    print("=== Teste 1: Importações básicas ===")
    try:
        from models import Hotel, Attraction, DailyRoute, TransportMode, Solution
        print("✓ Importação de models bem-sucedida")
    except Exception as e:
        print(f"✗ Erro ao importar models: {e}")
        return False
    
    try:
        from utils import Parser, Transport, Config
        print("✓ Importação de utils bem-sucedida")
    except Exception as e:
        print(f"✗ Erro ao importar utils: {e}")
        return False
    
    return True

def test_file_existence():
    """Teste de existência de arquivos necessários"""
    print("\n=== Teste 2: Arquivos necessários ===")
    files_to_check = [
        "places/attractions.csv",
        "places/hotels.csv",
        "travel-times/attractions_matrix_WALK.csv",
        "travel-times/hotels_to_attractions_WALK_GOING.csv"
    ]
    
    all_exist = True
    for file_path in files_to_check:
        if os.path.exists(file_path):
            print(f"✓ {file_path} existe")
        else:
            print(f"✗ {file_path} NÃO existe")
            all_exist = False
    
    return all_exist

def test_data_loading():
    """Teste de carregamento de dados"""
    print("\n=== Teste 3: Carregamento de dados ===")
    try:
        from utils import Parser
        
        # Testar carregamento de atrações
        if os.path.exists("places/attractions.csv"):
            attractions = Parser.load_attractions("places/attractions.csv")
            print(f"✓ Carregado {len(attractions)} atrações")
        else:
            print("✗ Arquivo de atrações não encontrado")
            return False
        
        # Testar carregamento de hotéis
        if os.path.exists("places/hotels.csv"):
            hotels = Parser.load_hotels("places/hotels.csv")
            print(f"✓ Carregado {len(hotels)} hotéis")
        else:
            print("✗ Arquivo de hotéis não encontrado")
            return False
        
        # Testar carregamento de matrizes
        matrices_loaded = Parser.load_transport_matrices(".")
        if matrices_loaded:
            print("✓ Matrizes de transporte carregadas")
        else:
            print("✗ Erro ao carregar matrizes de transporte")
            return False
        
        return True
    except Exception as e:
        print(f"✗ Erro no carregamento de dados: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_basic_route_creation():
    """Teste de criação básica de rotas"""
    print("\n=== Teste 4: Criação básica de rotas ===")
    try:
        from models import Hotel, Attraction, DailyRoute, TransportMode
        
        # Criar hotel de teste
        hotel = Hotel(name="Test Hotel", price=100.0, rating=4.0)
        print("✓ Hotel criado")
        
        # Criar atração de teste
        attraction = Attraction(
            name="Test Attraction",
            neighborhood="Downtown",
            visit_time=60,
            cost=15.0,
            saturday_opening_time=9*60,
            saturday_closing_time=18*60,
            sunday_opening_time=10*60,
            sunday_closing_time=17*60,
            rating=4.5
        )
        print("✓ Atração criada")
        
        # Criar rota de teste
        route = DailyRoute(is_saturday=True)
        route.set_hotel(hotel)
        print("✓ Rota diária criada")
        
        return True
    except Exception as e:
        print(f"✗ Erro na criação de rotas: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_constructor():
    """Teste do construtor MOVNS"""
    print("\n=== Teste 5: Construtor MOVNS ===")
    try:
        from movns.constructor import MOVNSConstructor
        
        constructor = MOVNSConstructor(
            "places/attractions.csv",
            "places/hotels.csv", 
            "."
        )
        print("✓ Construtor MOVNS inicializado")
        
        # Testar geração de uma solução
        solutions = constructor.generate_initial_population(1)
        if solutions:
            print(f"✓ Gerada {len(solutions)} solução inicial")
        else:
            print("✗ Nenhuma solução inicial gerada")
            return False
        
        return True
    except Exception as e:
        print(f"✗ Erro no construtor MOVNS: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Função principal de teste"""
    print("=== DIAGNÓSTICO DE PROBLEMAS NO CÓDIGO ===")
    
    tests = [
        test_basic_imports,
        test_file_existence,
        test_data_loading,
        test_basic_route_creation,
        test_constructor
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Erro inesperado no teste: {e}")
            results.append(False)
    
    print("\n=== RESUMO DOS TESTES ===")
    passed = sum(results)
    total = len(results)
    print(f"Testes aprovados: {passed}/{total}")
    
    if passed == total:
        print("✓ Todos os testes passaram! O código parece estar funcionando.")
    else:
        print("✗ Alguns testes falharam. Verifique os erros acima.")
        
        # Sugestões de correção
        print("\n=== SUGESTÕES DE CORREÇÃO ===")
        if not results[1]:  # test_file_existence
            print("- Verifique se os arquivos de dados estão no lugar correto")
            print("- As matrizes de tempo de viagem devem estar em travel-times/")
        
        if not results[2]:  # test_data_loading
            print("- Verifique o formato dos arquivos CSV")
            print("- Pode haver problemas de encoding ou formato")
        
        if not results[4]:  # test_constructor
            print("- Problema na lógica de construção de soluções")
            print("- Pode estar em loop infinito ou com incompatibilidades")

if __name__ == "__main__":
    main()
