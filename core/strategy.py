import pandas as pd
import numpy as np

class TechnicalAnalysis:
    @staticmethod
    def calculate_indicators(prices_list):
        """Calcula RSI e Bollinger Bands usando Pandas"""
        if len(prices_list) < 20:
            return None
            
        df = pd.DataFrame(prices_list, columns=['close'])
        
        # RSI 14
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Bollinger Bands (20, 2)
        df['sma'] = df['close'].rolling(window=20).mean()
        df['std'] = df['close'].rolling(window=20).std()
        df['upper'] = df['sma'] + (df['std'] * 2)
        df['lower'] = df['sma'] - (df['std'] * 2)
        
        # Retorna a última linha como dict
        last_row = df.iloc[-1]
        return {
            'rsi': last_row['rsi'],
            'upper': last_row['upper'],
            'lower': last_row['lower'],
            'close': last_row['close']
        }

    @staticmethod
    def get_signal(indicators):
        """Define sinal de compra/venda baseado nos indicadores"""
        if indicators is None:
            return "AGUARDANDO", 0.0
            
        score = 0.5
        signal = "NEUTRO"
        
        rsi = indicators['rsi']
        price = indicators['close']
        
        # Lógica de Score
        if rsi < 30: score += 0.3      # Sobrevendido -> Bom
        elif rsi > 70: score -= 0.3    # Sobrecomprado -> Ruim
        
        if price < indicators['lower']: score += 0.2 # Abaixo da banda -> Reversão
        elif price > indicators['upper']: score -= 0.2
        
        # Definição do Sinal
        if score >= 0.75: signal = "COMPRA FORTE"
        elif score >= 0.6: signal = "COMPRA"
        elif score <= 0.25: signal = "VENDA FORTE"
        elif score <= 0.4: signal = "VENDA"
        
        return signal, score
