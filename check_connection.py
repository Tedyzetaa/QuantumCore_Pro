import os
import asyncio
import ccxt.async_support as ccxt
from dotenv import load_dotenv

async def check():
    load_dotenv()
    exchange = ccxt.binance({
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_SECRET_KEY'),
    })
    
    sandbox = os.getenv('BINANCE_SANDBOX_MODE', 'FALSE').upper() == 'TRUE'
    if sandbox: exchange.set_sandbox_mode(True)
    
    print(f"--- DIAGNÓSTICO ---")
    print(f"Modo Sandbox: {sandbox}")
    
    try:
        await exchange.load_markets()
        print("✅ Conexão com Binance: OK")
        bal = await exchange.fetch_balance()
        print(f"✅ Saldo USDT: {bal.get('USDT', {}).get('free', 0)}")
        
        # Testar um par específico
        market = exchange.market('SOL/USDT')
        print(f"✅ Par SOL/USDT Ativo: {market['active']}")
        
    except Exception as e:
        print(f"❌ ERRO: {e}")
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(check())