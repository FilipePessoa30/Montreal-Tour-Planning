#!/usr/bin/env python3
import sys
import os
import time

print("Testando carregamento individual de arquivos...")

try:
    print("1. Verificando arquivos de matriz...")
    travel_times_path = "travel-times"
    
    files_to_check = [
        "attractions_matrix_WALK.csv",
        "hotels_to_attractions_WALK_GOING.csv",
        "hotels_to_attractions_WALK_RETURNING.csv"
    ]
    
    for filename in files_to_check:
        filepath = os.path.join(travel_times_path, filename)
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            print(f"   ✓ {filename}: {size} bytes")
        else:
            print(f"   ✗ {filename}: Não encontrado")
    
    print("\n2. Testando carregamento simples de CSV...")
    import csv
    
    filepath = os.path.join(travel_times_path, "attractions_matrix_WALK.csv")
    with open(filepath, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        header = next(reader)
        print(f"   ✓ Header: {len(header)} colunas")
        
        row_count = 0
        for row in reader:
            row_count += 1
            if row_count >= 10:  # Para não demorar muito
                break
        print(f"   ✓ Primeiras {row_count} linhas lidas sem problemas")
    
    print("\n3. Testando parser personalizado...")
    from utils import Parser
    
    # Teste com arquivo pequeno primeiro
    print("   Tentando carregar uma matriz pequena...")
    matrix = []
    names = []
    
    start_time = time.time()
    result = Parser.parse_matrix_file(
        filepath,
        matrix,
        names,
        is_hotel_rows=False,
        is_hotel_cols=False,
        extract_names=True
    )
    load_time = time.time() - start_time
    
    print(f"   ✓ Resultado: {result}, tempo: {load_time:.2f}s")
    print(f"   ✓ Matrix size: {len(matrix)}x{len(matrix[0]) if matrix else 0}")
    print(f"   ✓ Names: {len(names)}")
    
except Exception as e:
    print(f"✗ Erro: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
