# 💎 QuantumCore Pro v45.0 - Elite Terminal

O QuantumCore Pro é um bot de trading algorítmico de alta performance para Binance Spot, focado em estratégias de reversão de tendência usando RSI e Bandas de Bollinger.

## 🚀 Novas Funcionalidades (v44 & v45)
- **Interface Responsiva**: Painéis redimensionáveis (PanedWindow) para melhor visualização.
- **Gráficos Avançados**: Integração com `mplfinance` mostrando Bandas de Bollinger, Médias Móveis e **Linha Verde de Preço de Entrada**.
- **Gestão de Risco Estrita**: Limite de 2 trades simultâneos de $21 (configurável).
- **Trava de Slot (Semaphore)**: Impede que o bot abra mais ordens que o permitido em sinais simultâneos.
- **Dashboard Financeiro**: Saldo em tempo real e PnL aberto com indicadores visuais de lucro/prejuízo.
- **Pânico Blindado**: Botão de emergência v41.1 que limpa posições e zera o cache.

## 🛠️ Requisitos
- Python 3.10+
- Bibliotecas: `customtkinter`, `ccxt`, `pandas`, `mplfinance`, `matplotlib`

## ⚙️ Configuração Rápida
1. Renomeie o arquivo `.env.example` para `.env` e insira suas chaves de API.
2. No arquivo `core/config.py`, ajuste os pares desejados (Ex: `RENDER/USDT`, `SOL/USDT`).
3. Execute o `main.py`.

## ⚠️ Aviso Legal
Este software é para fins educacionais. Negociar criptomoedas envolve alto risco. O desenvolvedor não se responsabiliza por perdas financeiras.