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
    
    # --- FILTRAGEM DE MOEDAS (VOLATILIDADE ALTA) ---
    # Mistura de Memes, AI e Layer 1s que balançam bastante
    PAIRS = [
        {'symbol': 'SOL/USDT'}, {'symbol': 'AVAX/USDT'}, {'symbol': 'NEAR/USDT'},  # L1s Clássicas
        {'symbol': 'SUI/USDT'}, {'symbol': 'SEI/USDT'}, {'symbol': 'APT/USDT'},    # L1s Novas (Hype)
        {'symbol': 'FET/USDT'}, {'symbol': 'RENDER/USDT'},             # IA (Tendência)
        {'symbol': 'PEPE/USDT'}, {'symbol': 'DOGE/USDT'}, {'symbol': 'WIF/USDT'},  # Memes (Onde o dinheiro rápido está)
        {'symbol': 'FTM/USDT'}, {'symbol': 'INJ/USDT'}              # Alta Beta
    ]
    
    # SEGURANÇA ALTCOIN
    MIN_24H_VOLUME = 10000000 # Mínimo 10 Milhões de dólares de volume
    
    # --- AJUSTE DE GATILHO ---
    RSI_OVERSOLD = 30          # Voltamos para 30 para pegar os "Dips" normais
    
    # --- GERENCIAMENTO DE RISCO ---
    TRADE_AMOUNT = 11.0      # Configuração ajustada ($11)
    MAX_OPEN_TRADES = 2      # 2 Slots de operação
    
    # --- SAÍDA E LUCRO ---
    TAKE_PROFIT = 0.021      # 2.1% (Alvo)
    STOP_LOSS = 0.025        # 2.5% (Damos corda para a moeda pular)
    
    # --- PROTEÇÃO (Break-even) ---
    USE_BREAK_EVEN = True    # Ativa o modo escudo
    BREAK_EVEN_TRIGGER = 0.008 # Sobe o stop pro 0x0 se bater 0.8% de lucro

    # --- TRAILING STOP (O Deixa Correr) ---
    USE_TRAILING_STOP = True
    TRAILING_ACTIVATION = 0.021   # Ativa o rastreio quando bater 2.1% de lucro
    TRAILING_CALLBACK = 0.003     # Vende se cair 0.3% do topo atingido
    
    # --- FILTROS DE TENDÊNCIA ---
    USE_EMA_FILTER = True         # Se True, só compra acima da EMA
    EMA_PERIOD = 200              # Tendência de longo prazo
    
    # --- MÉDIAS MÓVEIS (LEQUE DE TENDÊNCIA) ---
    USE_SMA_FILTER = True
    # Lista completa de médias solicitadas
    SMA_PERIODS = [3, 10, 20, 50, 100, 200, 500]
    
    # --- IMPORTANTE: DADOS HISTÓRICOS ---
    # Para calcular a SMA 500, precisamos de no mínimo 600 candles
    LIMIT_CANDLES = 600
    
    # --- FILTROS DE ESTRATÉGIA ---
    # Só opera se o preço estiver acima destas médias (Tendência Macro)
    MACRO_TREND_SMAS = [200, 500] 
    
    BTC_CRASH_LIMIT = -3.0     # Deixamos o BTC "respirar" mais antes de travar o bot
    ZOMBIE_TIMEOUT = 7200      # 2 horas em segundos

    # --- FILTROS DE QUALIDADE ---
    MIN_VOLUME_24H = 1000000.0  # (1 Milhão USD) Só opera moedas com alta liquidez