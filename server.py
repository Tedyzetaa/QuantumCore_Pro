import asyncio
import time
import queue
import logging
import sys
from core.engine import TradingEngine
from core.config import Config
from core.telegram_bot import TelegramManager

# Configuração de Log para aparecer no terminal
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)

async def main_server():
    print("☁️  INICIANDO QUANTUMCORE PRO - MODO SERVIDOR (HEADLESS)")
    print("-------------------------------------------------------")
    
    # 1. Carrega Configurações
    config = Config()
    
    # 2. Fila de mensagens (Necessária para o Engine, mesmo sem GUI)
    update_queue = queue.Queue()
    
    # 3. Inicializa Telegram
    print("📡 Conectando ao Telegram...")
    telegram = TelegramManager(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
    await telegram.start() # Inicia o bot
    
    # 4. Inicializa o Motor
    print("⚙️  Ligando os motores...")
    engine = TradingEngine(update_queue, config, telegram=telegram)
    engine.running = True
    
    # Envia aviso de subida
    await telegram.send_notification("☁️ **BOT ONLINE NA NUVEM**\n\nModo: Headless Server\nStatus: Monitorando 24/7 🚀")

    # 5. Loop Principal (Infinito)
    try:
        while True:
            # Executa um ciclo de trade
            await engine.trading_cycle()
            
            # Processa logs da fila (para mostrar no terminal preto do servidor)
            while not update_queue.empty():
                msg_type, msg_content = update_queue.get()
                if msg_type == 'log':
                    logging.info(f"[ENGINE] {msg_content}")
            
            # Pequena pausa para não fritar a CPU do servidor
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Parando servidor...")
        await telegram.send_notification("⚠️ **BOT DESLIGADO MANUALMENTE**")
        await telegram.stop()
    except Exception as e:
        print(f"❌ ERRO FATAL: {e}")
        await telegram.send_notification(f"☠️ **CRASH DO SISTEMA**: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main_server())
    except KeyboardInterrupt:
        pass