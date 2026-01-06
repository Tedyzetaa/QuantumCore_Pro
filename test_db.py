import sqlite3
import time

def injetar_trade_teste():
    db_path = 'trades_history.db'
    print(f"📂 Conectando ao banco: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 1. Garante que a tabela existe (igual ao Engine)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                side TEXT,
                price REAL,
                qty REAL,
                pnl REAL,
                timestamp TEXT
            )
        """)

        # 2. Dados do Trade de Teste
        symbol = "TESTE/USDT"
        price = 100.00
        qty = 0.5
        pnl = 5.50  # Lucro fictício de $5.50
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

        # 3. Inserção
        print("💉 Injetando trade de teste...")
        cursor.execute(
            "INSERT INTO trades (symbol, side, price, qty, pnl, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (symbol, 'SELL', price, qty, pnl, timestamp)
        )
        
        conn.commit()
        conn.close()
        print(f"✅ SUCESSO! Trade gravado: {symbol} | Lucro: ${pnl}")
        print("📱 AGORA: Vá no seu Telegram e digite /relatorio")
        
    except Exception as e:
        print(f"❌ ERRO no Banco de Dados: {e}")

if __name__ == "__main__":
    injetar_trade_teste()