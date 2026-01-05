# 🚀 QuantumCore Pro - Terminal de Trading de Alta Performance

QuantumCore Pro é um bot de trading algorítmico avançado focado em Altcoins, utilizando a API da Binance. O projeto evoluiu de um script simples para um terminal interativo completo com interface responsiva, monitoramento de RSI/Bollinger e gestão de risco em tempo real.

## 🛠️ Arquitetura do Sistema
- **Motor (Engine):** Assíncrono (Asyncio) para processamento paralelo de múltiplos pares.
- **Interface (UI):** CustomTkinter com layout dinâmico e redimensionável (PanedWindows).
- **Banco de Dados:** SQLite para persistência de histórico de trades.
- **Gráficos:** Integração com Matplotlib e MPLFinance para candles em tempo real.

---

## 📈 Histórico de Versões e Implementações

### v33.0 - Fundação
- Implementação da lógica base de monitoramento de múltiplos pares.
- Conexão via CCXT com suporte a Modo Sandbox.

### v34.0 - Estabilização de Interface
- Criação da interface inicial com CustomTkinter.
- Correção de bugs de sincronia entre a Thread da UI e o Loop Assíncrono do motor.

### v35.0 - Controle e Histórico (Fix de Botões)
- **Fix:** Correção do `AttributeError: stop` (adição dos métodos start/stop no motor).
- **Novo:** Implementação da barra lateral de Histórico de Trades.
- **Banco de Dados:** Integração com `trades_history.db` para salvar vendas realizadas.

### v36.0 - Terminal Interativo
- **Interatividade:** Implementação de eventos de clique nos pares para troca instantânea de gráfico.
- **Ordenação:** Adição de função de Sort nas colunas (RSI, Preço) por clique no cabeçalho.
- **Visual:** Paleta de cores "Deep Dark" para reduzir fadiga ocular.

### v36.5 - Restauração e Pânico
- **Segurança:** Reimplantação do **Botão de Pânico** (venda imediata de todo o portfólio).
- **Timeframes:** Adição de seletores de tempo gráfico (1m, 5m, 15m, 1h).
- **Correção:** Fix do erro "Market Closed" através da sincronização de `load_markets()`.

### v37.0 - Layout Flexível e Dashboard Financeiro
- **Responsividade:** Uso de `PanedWindows` para permitir que o usuário arraste e redimensione os campos com o mouse.
- **Financeiro:** Dashboard em tempo real mostrando Saldo (USDT) e PnL Aberto (Lucro/Prejuízo flutuante).

### v38.0 - Cérebro Visual de Status
- **Status Engine:** Implementação de estados inteligentes: `NEUTRO`, `COMPRA!`, `COMPRADO`, `VENDENDO (T)` e `COOLDOWN`.
- **Feedback Visual:** Linhas coloridas na tabela para identificar sinais de compra e operações ativas rapidamente.

### v39.5 - Conectividade Sênior (Versão Atual)
- **Sincronização:** Ajuste de `recvWindow` e carregamento de mercados para evitar rejeições da API.
- **Agressividade:** Parâmetros de RSI e filtros de segurança otimizados para maior frequência de trades em Altcoins.

---

## 🚀 Como Executar
1. Certifique-se de que o relógio do Windows está sincronizado.
2. Configure suas chaves no arquivo `.env`.
3. Inicialize o banco de dados: `python init_db.py`.
4. Execute o terminal: `python main.py`.

## ⚠️ Avisos de Segurança
- O **Botão de Pânico** zera todas as posições abertas no mercado a preço de mercado.
- O modo `SANDBOX` deve ser definido como `FALSE` para operações reais.

---
**Desenvolvido por:** Engenheiro Sênior & Equipe QuantumCore.