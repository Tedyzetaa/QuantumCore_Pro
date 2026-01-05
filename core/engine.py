import asyncio
import sqlite3
import json
import ccxt.async_support as ccxt
import pandas as pd
import time
import os

class TradingEngine:
    def __init__(self, update_queue, config):
        self.update_queue = update_queue
        self.config = config
        self.running = False
        self.active_trades = {}
        self.cooldown_list = {} # Guarda o tempo da última venda de cada moeda
        
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
                profit = (price - entry_price) / entry_price
                status = "COMPRADO"

                if profit >= self.config.TAKE_PROFIT:
                    self.update_queue.put(('log', f"💰 TAKE PROFIT ATINGIDO: {s} ({profit*100:.2f}%)"))
                    await self._sell(s, price)
                    # ADICIONA O COOLDOWN DE 5 MINUTOS (300 segundos)
                    self.cooldown_list[s] = now + 300 
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

    async def _sell(self, symbol, price):
        if symbol not in self.active_trades: return
        try:
            trade = self.active_trades[symbol]
            qty = trade['qty']
            # Ajuste de precisão (Binance exige isso)
            qty = self.exchange.amount_to_precision(symbol, qty)
            
            self.update_queue.put(('log', f"🔻 VENDENDO {symbol}..."))
            order = await self.exchange.create_market_sell_order(symbol, qty)
            
            # PnL Real
            avg_price = float(order.get('average', price))
            pnl = (avg_price - trade['entry']) * float(qty)
            
            self.update_queue.put(('log', f"✅ VENDA SUCESSO: {symbol} @ {avg_price} (PnL: ${pnl:.2f})"))
            
            del self.active_trades[symbol]
            self._save_state()
            
        except Exception as e:
            self.update_queue.put(('log', f"❌ ERRO VENDA {symbol}: {e}"))

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