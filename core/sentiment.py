import random
import logging

class SocialSentiment:
    def __init__(self):
        # Palavras-chave positivas para buscar (se usasse API real)
        self.keywords = ['moon', 'bullish', 'pump', 'gem', 'hold']
    
    def get_sentiment_score(self, symbol, volume_change_pct):
        """
        Retorna um score de 0 a 100.
        Como APIs gratuitas do Twitter estão bloqueadas, usamos uma 
        Huerística de Volume + Randomização Controlada para simular o Hype.
        """
        # Base: 50 (Neutro)
        score = 50
        
        # 1. Se o volume subiu muito, o hype social provavelmente é alto
        if volume_change_pct > 20: score += 20
        elif volume_change_pct > 50: score += 30
        elif volume_change_pct < -10: score -= 10
        
        # 2. Fator de Volatilidade Social (Simulação de Tweets)
        # Gera uma variação orgânica entre -10 e +10
        social_noise = random.randint(-10, 10)
        
        final_score = score + social_noise
        
        # Limites 0-100
        return max(0, min(100, final_score))
