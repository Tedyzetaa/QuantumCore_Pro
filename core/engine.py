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

    def _check_daily_limits(self):
        return True

    async def _process_pair(self, pair):
        # 1. Checa Limites Diários
        if not self._check_daily_limits(): return None 
        
        s = pair['symbol']

        # 2. --- NOVO: FILTRO DE VOLUME (Anti-Mico) ---
        # Só gastamos tempo analisando se a moeda tiver liquidez
        try:
            ticker = await self.exchange.fetch_ticker(s)
            quote_volume = ticker.get('quoteVolume', 0) # Volume em USDT
            
            if quote_volume < self.config.MIN_VOLUME_24H:
                return None
        except Exception:
            return None # Se der erro no ticker, ignora e segue

        try:
            # Baixa 600 candles para garantir o cálculo da SMA 500
            timeframe = getattr(self.config, 'TIMEFRAME', '1m')
            ohlcv = await self.exchange.fetch_ohlcv(s, timeframe, limit=self.config.LIMIT_CANDLES)
            if not ohlcv or len(ohlcv) < 500: return None # Proteção se a moeda for muito nova e não tiver 500 candles
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df.set_index(pd.to_datetime(df['timestamp'], unit='ms'), inplace=True)
            
            # --- CÁLCULO DAS 7 MÉDIAS MÓVEIS ---
            for period in self.config.SMA_PERIODS:
                df[f'sma_{period}'] = df['close'].rolling(window=period).mean()

            # Outros indicadores (Calculados via Pandas para performance)
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # Bollinger Bands (20, 2)
            df['std'] = df['close'].rolling(20).std()
            df['lower_bb'] = df['sma_20'] - (df['std'] * 2)
            df['upper_bb'] = df['sma_20'] + (df['std'] * 2)
            
            # Pega os últimos valores
            last = df.iloc[-1]
            price = last['close']
            rsi = last['rsi']
            lower_bb = last['lower_bb']
            
            status = "NEUTRO"
            now = time.time()
            
            # --- LÓGICA DE VENDA E GESTÃO (TRAILING STOP + ZOMBIE) ---
            if s in self.active_trades and self.active_trades[s].get('status') != 'Pendente':
                trade = self.active_trades[s]
                entry_price = float(trade['entry'])
                
                # Recupera ou inicia o preço mais alto atingido (High Watermark)
                highest_price = trade.get('highest_price', 0)
                
                # Cálculo do Lucro Atual
                current_profit_pct = (price - entry_price) / entry_price
                status = "COMPRADO"

                # --- NOVA LÓGICA: BREAK-EVEN (ESCUDO) ---
                is_secured = trade.get('secured', False)
                
                # 1. Ativa o Escudo se bater 0.6%
                if self.config.USE_BREAK_EVEN and not is_secured:
                    if current_profit_pct >= self.config.BREAK_EVEN_TRIGGER:
                        trade['secured'] = True
                        self.active_trades[s] = trade
                        self._save_state()
                        self.update_queue.put(('log', f"🛡️ BREAK-EVEN ATIVADO: {s} (Trade protegido no 0x0)"))
                        if self.telegram:
                            asyncio.create_task(self.telegram.send_notification(f"🛡️ **ESCUDO ATIVADO**\n\nBlindando trade em {s}!\nSe cair, saímos no 0x0."))

                # 2. Executa o Stop (Dinâmico)
                # Se estiver protegido (secured), o Stop é o preço de entrada (+0.1% para pagar taxas)
                # Se NÃO estiver protegido, o Stop é o Configurado (1.5%)
                stop_price = entry_price * 1.001 if is_secured else entry_price * (1 - self.config.STOP_LOSS)
                
                if price <= stop_price:
                    reason = "BREAK_EVEN_EXIT" if is_secured else "STOP_LOSS"
                    # Pequeno filtro: Se for break-even, só sai se o lucro for realmente baixo/zero
                    await self._sell(s, price, df, reason=reason)
                    self.cooldown_list[s] = time.time() + 300
                    return None

                # --- A. LÓGICA DO TRAILING STOP ---
                if self.config.USE_TRAILING_STOP:
                    # 1. Ativação: Se bateu a ativação e ainda não ativou
                    if highest_price == 0 and current_profit_pct >= self.config.TRAILING_ACTIVATION:
                        trade['highest_price'] = price
                        self.active_trades[s] = trade # Salva no dict
                        self._save_state()
                        self.update_queue.put(('log', f"🚀 TRAILING ATIVADO: {s} em {current_profit_pct*100:.2f}%"))
                        
                        if self.telegram:
                            asyncio.create_task(self.telegram.send_notification(f"🚀 **TRAILING ATIVADO**\n\n💎 Par: `{s}`\n📈 Lucro Atual: *{current_profit_pct*100:.2f}%*\n👀 Acompanhando a alta..."))

                    # 2. Acompanhamento: Se já está ativo
                    elif highest_price > 0:
                        # Se o preço subiu mais, atualiza o topo
                        if price > highest_price:
                            trade['highest_price'] = price
                            self.active_trades[s] = trade
                            self._save_state()
                        
                        # Verifica se caiu X% do topo (O Callback)
                        pullback = (highest_price - price) / highest_price
                        if pullback >= self.config.TRAILING_CALLBACK:
                            self.update_queue.put(('log', f"💰 TRAILING STOP HIT: {s} (Topo: {highest_price})"))
                            await self._sell(s, price, df, reason="TRAILING_PROFIT")
                            self.cooldown_list[s] = now + 300
                            return None

                # --- B. TAKE PROFIT FIXO (Fallback se Trailing desligado) ---
                take_profit_target = getattr(self.config, 'TAKE_PROFIT', 0.025)
                if not self.config.USE_TRAILING_STOP and current_profit_pct >= take_profit_target:
                     await self._sell(s, price, df, reason="TAKE_PROFIT")
                     self.cooldown_list[s] = now + 300
                     return None

                # --- C. ZOMBIE KILLER (Só mata se NÃO estiver no Trailing Lucrativo) ---
                entry_time = trade.get('time', time.time())
                duration = now - entry_time
                if highest_price == 0 and duration >= self.config.ZOMBIE_TIMEOUT:
                    self.update_queue.put(('log', f"🧟 ZOMBIE KILLER: Fechando {s} após {int(duration/3600)}h de tédio..."))
                    await self._sell(s, price, df, reason="ZOMBIE")
                    self.cooldown_list[s] = now + 600 # Cooldown maior para moedas zumbis
                    return None
            
            # --- LÓGICA DE COMPRA (STRATEGY: GOLDEN ARRAY) ---
            if self.running and s not in self.active_trades:
                if len(self.active_trades) >= self.config.MAX_OPEN_TRADES: 
                    status = "NEUTRO (Saturado)"
                elif s in self.cooldown_list and now < self.cooldown_list[s]:
                    remaining = int(self.cooldown_list[s] - now)
                    status = f"WAIT ({remaining}s)"
                else:
                    # 1. FILTRO MACRO (SEGURANÇA):
                    # O preço deve estar acima das "Muralhas" (200 e 500).
                    is_bull_trend = (price > last['sma_200']) and (price > last['sma_500'])

                    # 2. FILTRO DE MOMENTO (PULLBACK):
                    # Queremos comprar barato, então o preço deve ter recuado abaixo das médias curtas.
                    is_pullback = (price < last['sma_20']) 

                    # GATILHO FINAL:
                    # Tendência de Alta (Macro) + Recuo (Pullback) + RSI Barato + Bollinger Estourada
                    if is_bull_trend and is_pullback and rsi < self.config.RSI_OVERSOLD and price <= lower_bb:
                        status = "COMPRA FORTE"
                        self.update_queue.put(('log', f"🚀 SINAL FORTE em {s}: Acima da SMA500/200 + RSI {rsi:.1f}"))
                        self.active_trades[s] = {'entry': price, 'status': 'Pendente'} 
                        await self._buy(s, price, df)
            
            return {'symbol': s, 'price': price, 'rsi': rsi, 'df': df, 'status': status, 'trade_info': self.active_trades.get(s)}
        except Exception as e:
            # self.update_queue.put(('log', f"Erro em {s}: {e}"))
            return None

    async def _sell(self, symbol, price, df=None, reason="PROFIT"):
        try:
            if symbol not in self.active_trades: return

            # --- 1. Lógica de Precisão e Venda na Binance ---
            bal = await self.exchange.fetch_balance()
            coin = symbol.split('/')[0]
            actual_balance = float(bal.get(coin, {}).get('free', 0))
            qty_to_sell = min(float(self.active_trades[symbol]['qty']), actual_balance)
            precise_qty = self.exchange.amount_to_precision(symbol, qty_to_sell)

            # Ajuste fino se arredondamento passar do saldo
            if float(precise_qty) > actual_balance:
                market = self.exchange.market(symbol)
                step_size = market['limits']['amount']['min']
                precise_qty = self.exchange.amount_to_precision(symbol, actual_balance - step_size)

            self.update_queue.put(('log', f"🔻 VENDA ({reason}): {symbol} Qtd: {precise_qty}"))
            order = await self.exchange.create_market_sell_order(symbol, precise_qty)
            
            # --- 2. Cálculos Financeiros ---
            trade_data = self.active_trades[symbol]
            entry_price = trade_data['entry']
            real_sell_price = float(order.get('average', price))
            pnl = (real_sell_price - entry_price) * float(precise_qty)
            pnl_pct = ((real_sell_price - entry_price) / entry_price) * 100

            self.update_queue.put(('log', f"✅ VENDA SUCESSO: {symbol} | Lucro: ${pnl:.2f} ({pnl_pct:.2f}%)"))

            # --- 3. GRAVAÇÃO NO BANCO DE DADOS (A CORREÇÃO) ---
            try:
                conn = sqlite3.connect('trades_history.db')
                cursor = conn.cursor()
                # Garante que a tabela existe
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT,
                        side TEXT,
                        price REAL,
                        qty REAL,
                        pnl REAL,
                        timestamp TEXT
                    )
                """)
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    "INSERT INTO trades (symbol, side, price, qty, pnl, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                    (symbol, 'SELL', real_sell_price, float(precise_qty), pnl, timestamp)
                )
                conn.commit()
                conn.close()
            except Exception as e_db:
                self.update_queue.put(('log', f"⚠️ Erro ao salvar histórico: {e_db}"))

            # --- 4. Notificação Telegram ---
            if self.telegram:
                emoji = "💰" if pnl >= 0 else "🧟"
                msg_title = "LUCRO (Take Profit)" if pnl >= 0 else "SAÍDA (Zombie/Stop)"
                msg = (f"{emoji} **{msg_title}**\n\n"
                       f"💎 Par: `{symbol}`\n"
                       f"💵 Venda: `${real_sell_price:.4f}`\n"
                       f"📈 Resultado: *${pnl:.2f}* ({pnl_pct:.2f}%)")
                asyncio.create_task(self.telegram.send_notification(msg))
                
                # NOVA LINHA: Gráfico de saída
                pnl_label = f"${pnl:.2f}"
                if df is not None:
                    asyncio.create_task(self.telegram.send_chart(symbol, df, f"VENDA ({reason})", price, pnl_label))

        except Exception as e:
            error_msg = str(e).lower()
            if "insufficient balance" in error_msg:
                self.update_queue.put(('log', f"⚠️ Saldo insuficiente para {symbol}. Limpando memória..."))
            else:
                self.update_queue.put(('log', f"❌ ERRO VENDA {symbol}: {e}"))
                return False
        
        # --- 5. Limpeza de Memória ---
        if symbol in self.active_trades:
            del self.active_trades[symbol]
            self._save_state()
        return True

    async def _buy(self, symbol, price, df=None):
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
                # NOVA LINHA: Envia o gráfico se o DF existir
                if df is not None:
                    asyncio.create_task(self.telegram.send_chart(symbol, df, "COMPRA", price))
            
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