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
        self.last_update_id = 0
        self.btc_health = {'status': 'OK', 'change_1h': 0.0}
        self.cooldown_list = {}
        
        self.exchange = ccxt.binance({
            'apiKey': config.API_KEY, 
            'secret': config.SECRET_KEY, 
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        if config.SANDBOX_MODE: self.exchange.set_sandbox_mode(True)
        
        self.portfolio = {'available_capital': 0.0, 'floating_pnl': 0.0, 'daily_pnl': 0.0, 'best_pair': "---"}
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
        self.update_queue.put(('bot_state', True))
        self.update_queue.put(('log', "▶ MOTOR INICIADO - BUSCANDO ENTRADAS"))

    async def stop(self):
        self.running = False
        self.update_queue.put(('bot_state', False))
        self.update_queue.put(('log', "⏸ MOTOR PAUSADO"))

    async def _process_pair(self, pair):
        s = pair['symbol']
        try:
            ohlcv = await self.exchange.fetch_ohlcv(s, '1m', limit=100)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df.set_index(pd.to_datetime(df['timestamp'], unit='ms'), inplace=True)
            
            # Indicadores essenciais para o gráfico
            df['ma20'] = df['close'].rolling(20).mean()
            df['std'] = df['close'].rolling(20).std()
            df['lower_bb'] = df['ma20'] - (df['std'] * 2)
            df['upper_bb'] = df['ma20'] + (df['std'] * 2)
            
            delta = df['close'].diff()
            df['rsi'] = 100 - (100 / (1 + (delta.where(delta > 0, 0).rolling(14).mean() / (abs(delta.where(delta < 0, 0)).rolling(14).mean() + 1e-9))))
            
            row = df.iloc[-1]
            price, rsi, lower_bb, upper_bb = row['close'], row['rsi'], row['lower_bb'], row['upper_bb']
            
            # --- DEFINIÇÃO DO STATUS REAL ---
            status = "NEUTRO"
            
            if s in self.active_trades:
                trade = self.active_trades[s]
                # Se o lucro subiu acima da ativação do Trailing
                profit = (price - trade['entry']) / trade['entry']
                if profit >= self.config.TRAILING_ACTIVATION:
                    status = "VENDENDO (T)"
                elif trade.get('breakeven_active'):
                    status = "PROTEGIDO"
                else:
                    status = "COMPRADO"
            else:
                if self.running:
                    if rsi < self.config.RSI_OVERSOLD:
                        if price <= lower_bb * 1.005: # Margem de 0.5% da banda
                            if len(self.active_trades) < self.config.MAX_OPEN_TRADES:
                                status = "COMPRA!"
                                await self._buy(s, price)
                            else:
                                self.update_queue.put(('log', f"⚠️ Limite de trades atingido ({s} ignorada)"))
                
                if s in self.cooldown_list:
                    status = "COOLDOWN"

            return {
                'symbol': s, 
                'price': price, 
                'rsi': rsi, 
                'df': df, 
                'status': status # Enviando o status para a interface
            }
        except: return None

    async def _buy(self, symbol, price):
        if not self.running: return

        try:
            # 1. VERIFICAÇÃO DE STATUS DO MERCADO
            market = self.exchange.market(symbol)
            if not market['active']:
                self.update_queue.put(('log', f"⚠️ {symbol} está em manutenção na Binance."))
                return

            # 2. CALCULO DE QUANTIDADE COM PRECISÃO
            amount = self.exchange.amount_to_precision(symbol, self.config.TRADE_AMOUNT / price)
            
            # 3. ENVIO DA ORDEM COM SINCRONIZAÇÃO DE HORÁRIO
            self.update_queue.put(('log', f"🛒 Tentando comprar {symbol}..."))
            order = await self.exchange.create_market_buy_order(symbol, amount, {'recvWindow': 60000})
            
            real_price = float(order.get('average', price))
            self.active_trades[symbol] = {
                'entry': real_price,
                'qty': float(amount),
                'highest': real_price,
                'sl': real_price * 0.96,
                'entry_time': time.time()
            }
            self._save_state()
            self.update_queue.put(('log', f"🚀 COMPRA REALIZADA: {symbol} @ {real_price}"))
            
        except Exception as e:
            self.update_queue.put(('log', f"❌ ERRO COMPRA: {e}"))

    async def handle_commands(self):
        pass

    async def trading_cycle(self):
        try:
            await self.handle_commands()
            tasks = [self._process_pair(p) for p in self.config.PAIRS]
            results = await asyncio.gather(*tasks)
            valid = [r for r in results if r]
            
            if valid:
                # --- CÁLCULO DE PNL E SALDO ---
                bal = await self.exchange.fetch_balance()
                self.portfolio['available_capital'] = float(bal.get('USDT', {}).get('free', 0))
                
                floating_pnl = 0.0
                for s, t in self.active_trades.items():
                    for r in valid:
                        if r['symbol'] == s:
                            pnl = (r['price'] - t['entry']) * t['qty']
                            floating_pnl += pnl
                
                self.portfolio['floating_pnl'] = floating_pnl
                self.update_queue.put(('portfolio', self.portfolio))
                self.update_queue.put(('pairs_data', valid))
        except Exception as e:
            self.update_queue.put(('log', f"Erro Ciclo: {e}"))

    async def emergency_close_all(self):
        self.running = False
        self.update_queue.put(('log', "🚨 EXECUTANDO PÂNICO DEFINITIVO..."))
        try:
            bal = await self.exchange.fetch_balance()
            for s in list(self.active_trades.keys()):
                coin = s.split('/')[0]
                qty = float(bal.get(coin, {}).get('free', 0))
                if qty > 0:
                    await self.exchange.create_market_sell_order(s, self.exchange.amount_to_precision(s, qty))
            self.active_trades = {}
            if os.path.exists('active_trades.json'): os.remove('active_trades.json')
            self.update_queue.put(('log', "✅ TODAS AS POSIÇÕES ZERADAS."))
        except Exception as e:
            self.update_queue.put(('log', f"❌ ERRO NO PÂNICO: {e}"))