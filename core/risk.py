import logging
from decimal import Decimal
from core.config import Config

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self):
        self.daily_pnl = Decimal('0.0')
        self.trades_count_today = 0

    def check_trade_allowed(self, current_capital, active_trades_count):
        """Verifica travas de segurança antes de abrir trade"""
        
        # 1. Trava de Trades Simultâneos
        if active_trades_count >= Config.MAX_CONCURRENT_TRADES:
            return False, "Max Trades Atingido"
            
        # 2. Trava de Drawdown (Proteção de Capital)
        # Se o capital cair abaixo de 80% do inicial, para tudo.
        if current_capital < (Config.INITIAL_CAPITAL * Decimal('0.8')):
            return False, "Circuit Breaker: Drawdown Excessivo"

        return True, "OK"

    def calculate_position_size(self, capital, price):
        """Calcula tamanho da posição baseado no risco"""
        entry_price = Decimal(str(price))
        
        # Valor a arriscar (Ex: $10.000 * 2% = $200 em risco)
        # Tamanho da Posição = Capital * 0.1 (Exemplo simplificado de alocação de 10% da banca por trade)
        # Em produção real, usaria cálculo baseado na distância do Stop Loss.
        
        position_value = capital * Decimal('0.10') 
        quantity = position_value / entry_price
        
        stop_loss = entry_price * (1 - Config.STOP_LOSS_PCT)
        take_profit = entry_price * (1 + Config.TAKE_PROFIT_PCT)
        
        return {
            'qty': float(quantity),
            'value': float(position_value),
            'sl': float(stop_loss),
            'tp': float(take_profit)
        }
