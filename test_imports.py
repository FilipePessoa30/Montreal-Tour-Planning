#!/usr/bin/env python3
import sys

print("Testando importações básicas...")

try:
    print("1. Testando pandas...")
    import pandas as pd
    print("   ✓ pandas importado com sucesso")
except Exception as e:
    print(f"   ✗ Erro com pandas: {e}")
    sys.exit(1)

try:
    print("2. Testando models...")
    import models
    print("   ✓ models importado com sucesso")
except Exception as e:
    print(f"   ✗ Erro com models: {e}")
    sys.exit(1)

try:
    print("3. Testando utils...")
    import utils
    print("   ✓ utils importado com sucesso")
except Exception as e:
    print(f"   ✗ Erro com utils: {e}")
    sys.exit(1)

print("Todos os módulos básicos funcionaram!")
