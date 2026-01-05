import json
import os

def fix_json_slots():
    path = 'active_trades.json'
    if os.path.exists(path):
        with open(path, 'r') as f:
            data = json.load(f)
        
        if len(data) > 2:
            print(f"⚠️ Detectados {len(data)} trades ativos. O limite é 2.")
            # Mantém apenas os 2 primeiros trades para o bot não se perder
            new_data = dict(list(data.items())[:2])
            with open(path, 'w') as f:
                json.dump(new_data, f)
            print("✅ JSON ajustado para os 2 primeiros trades. Venda o 3º manualmente na Binance!")
        else:
            print("✅ Slots estão dentro do limite.")

if __name__ == "__main__":
    fix_json_slots()