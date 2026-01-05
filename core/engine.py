import asyncio
import sqlite3
import json
import ccxt.async_support as ccxt
import pandas as pd
import time
import os

class TradingEngine:
    def __init__(self, update_queue, config, telegram=None):
        self.update_queue = update_queue
        self.config = config
        self.running = False
        self.active_trades = {}
        self.cooldown_list = {} # Guarda o tempo da última venda de cada moeda
        self.telegram = telegram
        
        self.exchange = ccxt.binance({
            'apiKey': config.API_KEY, 
            'secret': config.SECRET_KEY, 
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        if config.SANDBOX_MODE: self.exchange.set_sandbox_mode(True)
        
        self.portfolio = {'available_capital': 0.0, 'floating_pnl': 0.0}
        self._load_state()

    def _load_state(self):
        if os.path.exists('active_trades.json'):
            try:
                with open('active_trades.json', 'r') as f: self.active_trades = json.load(f)
            except: self.active_trades = {}

    def _save_state(self):
        try:
            with open('active_trades.json', 'w') as f: json.dump(self.active_trades, f)
        except: pass

    async def start(self):
        await self.exchange.load_markets()
        self.running = True
        self.update_queue.put(('log', "▶ MOTOR INICIADO - BUSCANDO ENTRADAS"))

    async def stop(self):
        self.running = False
        self.update_queue.put(('log', "⏸ MOTOR PAUSADO"))

    async def _process_pair(self, pair):
        s = pair['symbol']
        try:
            ohlcv = await self.exchange.fetch_ohlcv(s, '1m', limit=100)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df.set_index(pd.to_datetime(df['timestamp'], unit='ms'), inplace=True)
            
            # Indicadores de Elite
            df['ma20'] = df['close'].rolling(20).mean()
            df['std'] = df['close'].rolling(20).std()
            df['lower_bb'] = df['ma20'] - (df['std'] * 2)
            df['upper_bb'] = df['ma20'] + (df['std'] * 2)
            delta = df['close'].diff()
            df['rsi'] = 100 - (100 / (1 + (delta.where(delta > 0, 0).rolling(14).mean() / (abs(delta.where(delta < 0, 0)).rolling(14).mean() + 1e-9))))
            
            row = df.iloc[-1]
            price, rsi, lower_bb = row['close'], row['rsi'], row['lower_bb']
            
            status = "NEUTRO"
            now = time.time()
            
            # --- LÓGICA DE VENDA (TAKE PROFIT 2.5%) ---
            if s in self.active_trades and self.active_trades[s].get('status') != 'Pendente':
                trade = self.active_trades[s]
                entry_price = trade['entry']
                entry_time = trade.get('time', time.time()) # Pega a hora da compra
                profit = (price - entry_price) / entry_price
                status = "COMPRADO"

                # 1. Verificação de Take Profit
                if profit >= self.config.TAKE_PROFIT:
                    self.update_queue.put(('log', f"💰 TAKE PROFIT: {s} ({profit*100:.2f}%)"))
                    await self._sell(s, price)
                    self.cooldown_list[s] = now + 300 
                    return None

                # 2. ZOMBIE KILLER (Nova/Reativada)
                duration = now - entry_time
                if duration >= self.config.ZOMBIE_TIMEOUT:
                    self.update_queue.put(('log', f"🧟 ZOMBIE KILLER: Fechando {s} após {int(duration/3600)}h de tédio..."))
                    await self._sell(s, price)
                    await self._sell(s, price, reason="ZOMBIE")
                    self.cooldown_list[s] = now + 600 # Cooldown maior para moedas zumbis
                    return None
            
            # --- LÓGICA DE COMPRA COM TRAVA DE 5 MINUTOS ---
            if self.running and s not in self.active_trades:
                # Verifica se a moeda está no "castigo" de 5 minutos
                if s in self.cooldown_list:
                    if now < self.cooldown_list[s]:
                        remaining = int(self.cooldown_list[s] - now)
                        status = f"WAIT ({remaining}s)"
                        return {'symbol': s, 'price': price, 'rsi': rsi, 'df': df, 'status': status, 'trade_info': None}
                    else:
                        del self.cooldown_list[s] # Tempo acabou, pode comprar de novo

                # Verificação normal de compra
                if len(self.active_trades) < self.config.MAX_OPEN_TRADES:
                    if rsi < self.config.RSI_OVERSOLD and price <= lower_bb * 1.005:
                        status = "COMPRA!"
                        # Bloqueio imediato para evitar que outra task entre aqui
                        # Adicionamos o par temporariamente para ocupar o slot
                        self.active_trades[s] = {'entry': price, 'status': 'Pendente'} 
                        await self._buy(s, price)
                else:
                    status = "NEUTRO (Saturado)"
            
            return {'symbol': s, 'price': price, 'rsi': rsi, 'df': df, 'status': status, 'trade_info': self.active_trades.get(s)}
        except: return None

    async def _sell(self, symbol, price, reason="PROFIT"):
        try:
            if symbol not in self.active_trades: return
            
            # 1. Pega o saldo real diretamente da exchange para evitar erro de cache
            bal = await self.exchange.fetch_balance()
            coin = symbol.split('/')[0]
            actual_balance = float(bal.get(coin, {}).get('free', 0))
            
            # 2. Compara com o que temos no JSON e usa o MENOR valor 
            # (Segurança contra poeira/dust ou taxas de BNB)
            qty_to_sell = min(float(self.active_trades[symbol]['qty']), actual_balance)
            
            # 3. USA TRUNCATE (Arredonda sempre para baixo conforme as regras da exchange)
            # O CCXT já faz isso com amount_to_precision se o mercado estiver carregado
            precise_qty = self.exchange.amount_to_precision(symbol, qty_to_sell)
            
            # Verificação extra: se após a precisão o valor ficou maior que o saldo, reduz um step
            if float(precise_qty) > actual_balance:
                market = self.exchange.market(symbol)
                step_size = market['limits']['amount']['min']
                precise_qty = self.exchange.amount_to_precision(symbol, actual_balance - step_size)

            self.update_queue.put(('log', f"🔻 VENDA SEGURA: {symbol} Qtd: {precise_qty}"))
            
            order = await self.exchange.create_market_sell_order(symbol, precise_qty)
            
            self.update_queue.put(('log', f"✅ VENDA EXECUTADA: {symbol}"))
            
            trade = self.active_trades[symbol]
            pnl_pct = ((float(price) - float(trade['entry'])) / float(trade['entry'])) * 100
            emoji = "💰" if "PROFIT" in reason else "🧟"
            msg = f"{emoji} **VENDA EXECUTADA** ({reason})\n\n💎 Par: `{symbol}`\n📈 Lucro: *{pnl_pct:.2f}%*\n💰 Saída: `${price:.4f}`"
            if self.telegram:
                asyncio.create_task(self.telegram.send_notification(msg))
            
        except Exception as e:
            error_msg = str(e).lower()
            if "insufficient balance" in error_msg:
                self.update_queue.put(('log', f"⚠️ Saldo insuficiente para vender {symbol}. Removendo da memória..."))
                # Se não tem saldo, não adianta tentar de novo. Removemos do JSON.
            else:
                self.update_queue.put(('log', f"❌ ERRO VENDA {symbol}: {e}"))
                return False # Mantém no JSON para tentar de novo se for erro de rede
        
        # REMOÇÃO DA MEMÓRIA (Executa se vender com sucesso OU se der erro de saldo insuficiente)
        if symbol in self.active_trades:
            del self.active_trades[symbol]
            self._save_state()
        return True

    async def _buy(self, symbol, price):
        if not self.running: return

        try:
            # FORÇAR RECARREGAMENTO DE MERCADOS (Resolve o erro de Market Closed)
            await self.exchange.load_markets(True) 
            
            if symbol not in self.exchange.markets:
                self.update_queue.put(('log', f"⚠️ {symbol} não encontrado na Binance."))
                return

            market = self.exchange.market(symbol)
            
            # Verificar se o par está ativo e permite ordens a mercado
            if not market.get('active', False):
                self.update_queue.put(('log', f"⚠️ Mercado {symbol} está suspenso/fechado."))
                return

            # Cálculo de quantidade com precisão rigorosa
            amount_usdt = self.config.TRADE_AMOUNT
            amount = self.exchange.amount_to_precision(symbol, amount_usdt / price)
            
            self.update_queue.put(('log', f"🛒 Enviando ordem real para {symbol}..."))
            
            # Envio com sincronização de tempo (recvWindow)
            order = await self.exchange.create_market_buy_order(symbol, amount, {'recvWindow': 60000})
            
            real_price = float(order.get('average', price))
            self.active_trades[symbol] = {
                'entry': real_price, 
                'qty': float(amount), 
                'sl': real_price * 0.96,
                'time': time.time()
            }
            self._save_state()
            self.update_queue.put(('log', f"🚀 COMPRA SUCESSO: {symbol} @ {real_price}"))
            
            msg = f"🟢 **COMPRA EXECUTADA**\n\n💎 Par: `{symbol}`\n💵 Preço: `${real_price:.4f}`\n🚀 Slots: {len(self.active_trades)}/2"
            if self.telegram:
                asyncio.create_task(self.telegram.send_notification(msg))
            
        except Exception as e:
            # Se der erro de mercado fechado aqui, o bot pausa o par por 1 minuto
            self.update_queue.put(('log', f"❌ ERRO API: {e}"))
            if "closed" in str(e).lower():
                self.update_queue.put(('log', "💡 Dica: Verifique se BINANCE_SANDBOX_MODE está FALSE no .env"))

    async def trading_cycle(self):
        try:
            # 1. Verificação de segurança ANTES de começar o ciclo
            if len(self.active_trades) >= self.config.MAX_OPEN_TRADES:
                # Se já atingiu o limite, apenas atualiza preços e PnL, não busca novas compras
                self.update_queue.put(('log', f"✅ Limite de slots atingido ({self.config.MAX_OPEN_TRADES}/{self.config.MAX_OPEN_TRADES}). Monitorando saídas..."))
                # Reduzimos a carga processando apenas o que já está comprado
                tasks = [self._process_pair(p) for p in self.config.PAIRS if p['symbol'] in self.active_trades]
            else:
                tasks = [self._process_pair(p) for p in self.config.PAIRS]

            results = await asyncio.gather(*tasks)
            valid = [r for r in results if r]
            if valid:
                bal = await self.exchange.fetch_balance()
                self.portfolio['available_capital'] = float(bal.get('USDT', {}).get('free', 0))
                
                f_pnl = 0.0
                for r in valid:
                    if r['symbol'] in self.active_trades and 'qty' in self.active_trades[r['symbol']]:
                        f_pnl += (r['price'] - self.active_trades[r['symbol']]['entry']) * self.active_trades[r['symbol']]['qty']

                self.portfolio['floating_pnl'] = f_pnl
                self.update_queue.put(('portfolio', self.portfolio))
                self.update_queue.put(('pairs_data', valid))
                
                conn = sqlite3.connect('trades_history.db')
                hist = conn.execute("SELECT symbol, pnl FROM trades WHERE side='SELL' ORDER BY id DESC LIMIT 10").fetchall()
                conn.close()
                self.update_queue.put(('trade_history', hist))
        except Exception as e:
            self.update_queue.put(('log', f"Erro Ciclo: {e}"))

    async def emergency_close_all(self):
        self.running = False
        self.update_queue.put(('log', "🚨 PÂNICO FORCE v41.1..."))
        try:
            await self.exchange.load_markets()
            bal = await self.exchange.fetch_balance()
            for s in list(self.active_trades.keys()):
                coin = s.split('/')[0]
                qty = float(bal.get(coin, {}).get('free', 0))
                if qty > 0:
                    ticker = await self.exchange.fetch_ticker(s)
                    if (qty * ticker['last']) > 11.0:
                        precise_qty = self.exchange.amount_to_precision(s, qty)
                        await self.exchange.create_market_sell_order(s, precise_qty)
                        self.update_queue.put(('log', f"✅ {s} zerado."))
            self.active_trades = {}; self._save_state()
            self.update_queue.put(('log', "🏁 PÂNICO CONCLUÍDO."))
        except Exception as e: self.update_queue.put(('log', f"❌ ERRO PÂNICO: {e}"))