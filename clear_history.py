import json
import os

def reset_active_trades():
    file_path = 'active_trades.json'
    # Cria um dicionário vazio
    empty_data = {}
    
    try:
        with open(file_path, 'w') as f:
            json.dump(empty_data, f)
        print("✅ Memória de trades ativos (JSON) zerada com sucesso!")
        print("💡 O bot agora ignora qualquer trade aberto anteriormente.")
    except Exception as e:
        print(f"❌ Erro ao limpar o arquivo: {e}")

if __name__ == "__main__":
    reset_active_trades()