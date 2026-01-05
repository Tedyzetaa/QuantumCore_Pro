import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    APP_NAME = "QuantumCore v32.0 [ALTCOIN SAFE]"
    API_KEY = os.getenv("BINANCE_API_KEY")
    SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")
    SANDBOX_MODE = os.getenv("BINANCE_SANDBOX_MODE", "TRUE").upper() == "TRUE"
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    
    # Lista focada em Altcoins com boa liquidez
    PAIRS = [
        {'symbol': 'SOL/USDT'}, {'symbol': 'ETH/USDT'}, {'symbol': 'BNB/USDT'},
        {'symbol': 'AVAX/USDT'}, {'symbol': 'NEAR/USDT'}, {'symbol': 'DOT/USDT'},
        {'symbol': 'LINK/USDT'}, {'symbol': 'POL/USDT'}, {'symbol': 'ADA/USDT'},
        {'symbol': 'LTC/USDT'}, {'symbol': 'XRP/USDT'}, {'symbol': 'ATOM/USDT'},
        {'symbol': 'GALA/USDT'}, {'symbol': 'INJ/USDT'}, {'symbol': 'OP/USDT'},
        {'symbol': 'ARB/USDT'}, {'symbol': 'FET/USDT'}, {'symbol': 'RENDER/USDT'}
    ]
    
    # SEGURANÇA ALTCOIN
    MIN_24H_VOLUME = 10000000 # Mínimo 10 Milhões de dólares de volume
    RSI_OVERSOLD = 33          # Aumentamos de 30 para 35 para dar mais chances de entrada
    MAX_OPEN_TRADES = 2
    TRADE_AMOUNT = 21.0
    EMA_FILTER_ENABLED = False # Vamos desativar o filtro de EMA 200 temporariamente para testar
    
    # ESTRATÉGIA DE LUCRO (MODO SCALPER)
    TAKE_PROFIT = 0.025        # Alvo de 2.5%
    BREAKEVEN_TRIGGER = 0.012  # Protege com 1.2%
    TRAILING_ACTIVATION = 0.018 # Ativa venda com 1.8%
    TRAILING_CALLBACK = 0.006   # Vende se recuar 0.6%
    
    BTC_CRASH_LIMIT = -3.0     # Deixamos o BTC "respirar" mais antes de travar o bot