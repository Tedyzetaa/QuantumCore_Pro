import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
import mplfinance as mpf
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import queue, threading, asyncio, time, os
from core.telegram_bot import TelegramManager

class MultiPairTradingInterface:
    def __init__(self, root, engine_class, config):
        self.root = root
        self.config = config
        self.update_queue = queue.Queue()
        self.telegram = TelegramManager(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
        self.engine = engine_class(self.update_queue, self.config, telegram=self.telegram)
        self.telegram.engine = self.engine
        self.loop = asyncio.new_event_loop()
        self.selected_symbol = self.config.PAIRS[0]['symbol']
        self.cached_data = {}
        
        self.fig, self.ax = plt.subplots(figsize=(8, 5), dpi=100)
        self.fig.patch.set_facecolor('#0e0e0e')
        self.ax.set_facecolor('#0e0e0e')
        
        self.setup_ui()
        self.root.after(100, self.process_queue)
        threading.Thread(target=self._run_async_loop, daemon=True).start()
        asyncio.run_coroutine_threadsafe(self.telegram.start(), self.loop)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _run_async_loop(self):
        asyncio.set_event_loop(self.loop)
        while True:
            try:
                self.loop.run_until_complete(self.engine.trading_cycle())
                time.sleep(1)
            except: pass

    def setup_ui(self):
        self.root.title("QuantumCore v44.0 - Elite Terminal")
        self.root.geometry("1500x950")
        
        # PANED WINDOW PRINCIPAL (Horizontal)
        self.main_pane = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg="#0a0a0a", sashwidth=6, sashrelief=tk.RAISED)
        self.main_pane.pack(fill="both", expand=True)

        # SIDEBAR ESQUERDA
        self.sidebar = ctk.CTkFrame(self.main_pane, corner_radius=0, fg_color="#121212")
        self.main_pane.add(self.sidebar, width=380)

        # Dashboard Financeiro
        self.fin_frame = ctk.CTkFrame(self.sidebar, fg_color="#1e1e1e", corner_radius=12)
        self.fin_frame.pack(pady=15, padx=15, fill="x")
        self.lbl_cap = ctk.CTkLabel(self.fin_frame, text="Saldo: $0.00", font=("Orbitron", 18, "bold"), text_color="#00ffcc")
        self.lbl_cap.pack(pady=8)
        self.lbl_pnl = ctk.CTkLabel(self.fin_frame, text="PnL Aberto: $0.00", font=("Arial", 15, "bold"))
        self.lbl_pnl.pack(pady=5)

        # Controles
        btn_f = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        btn_f.pack(fill="x", padx=15)
        ctk.CTkButton(btn_f, text="▶ START", fg_color="#27ae60", width=110, command=self.start_bot).pack(side="left", padx=5, expand=True)
        ctk.CTkButton(btn_f, text="⏸ STOP", fg_color="#e67e22", width=110, command=self.stop_bot).pack(side="left", padx=5, expand=True)
        ctk.CTkButton(self.sidebar, text="🚨 PÂNICO GERAL", fg_color="#c0392b", font=("Arial", 13, "bold"), command=self.panic_bot).pack(pady=15, padx=20, fill="x")

        # Tabela de Mercado
        ctk.CTkLabel(self.sidebar, text="MERCADO ATIVO", font=("Arial", 11, "bold"), text_color="gray").pack()
        self.tree = ttk.Treeview(self.sidebar, columns=("P", "Pr", "R", "S"), show="headings", height=12)
        for c, h in zip(("P","Pr","R","S"), ("PAR","PREÇO","RSI","STATUS")):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=75, anchor="center")
        self.tree.pack(pady=5, padx=10, fill="x")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        
        # Tags de Cores
        self.tree.tag_configure('buy_signal', background='#27ae60', foreground='white')
        self.tree.tag_configure('bought', background='#2980b9', foreground='white')
        self.tree.tag_configure('selling', background='#d35400', foreground='white')

        # Histórico de Trades
        ctk.CTkLabel(self.sidebar, text="HISTÓRICO DE VENDAS", font=("Arial", 11, "bold"), text_color="gray").pack(pady=(15,0))
        self.tree_hist = ttk.Treeview(self.sidebar, columns=("H_P", "H_PnL"), show="headings", height=8)
        self.tree_hist.heading("H_P", text="PAR"); self.tree_hist.heading("H_PnL", text="LUCRO $")
        self.tree_hist.column("H_P", width=120); self.tree_hist.column("H_PnL", width=120)
        self.tree_hist.pack(pady=5, padx=10, fill="both", expand=True)

        # --- ÁREA DIREITA (Vertical Pane) ---
        self.right_pane = tk.PanedWindow(self.main_pane, orient=tk.VERTICAL, bg="#0a0a0a", sashwidth=6)
        self.main_pane.add(self.right_pane)

        # Topo: Gráfico
        self.chart_container = ctk.CTkFrame(self.right_pane, fg_color="#0e0e0e", corner_radius=0)
        self.right_pane.add(self.chart_container, height=650)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.chart_container)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=15, pady=15)

        # Base: Logs
        self.log_container = ctk.CTkFrame(self.right_pane, fg_color="#0a0a0a", corner_radius=0)
        self.right_pane.add(self.log_container, height=250)
        self.log_box = ctk.CTkTextbox(self.log_container, fg_color="#0e0e0e", text_color="#00ff88", font=("Consolas", 12))
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)

    def on_select(self, event):
        sel = self.tree.selection()
        if sel:
            self.selected_symbol = self.tree.item(sel[0], "values")[0]
            if self.selected_symbol in self.cached_data: self.render_chart(self.cached_data[self.selected_symbol])

    def process_queue(self):
        try:
            while not self.update_queue.empty():
                mtype, data = self.update_queue.get_nowait()
                if mtype == 'pairs_data':
                    for r in data:
                        self.cached_data[r['symbol']] = r
                        
                        # --- LÓGICA DE STATUS VISUAL (TRAILING) ---
                        display_status = r['status']
                        if r.get('trade_info'):
                            highest = r['trade_info'].get('highest_price', 0)
                            if highest > 0:
                                display_status = "🚀 TRAILING"
                        
                        tag = 'buy_signal' if "COMPRA" in r['status'] else ('bought' if "COMPRADO" in r['status'] or "TRAILING" in display_status else ('selling' if "VENDENDO" in r['status'] else ''))
                        found = False
                        for item in self.tree.get_children():
                            if self.tree.item(item, 'values')[0] == r['symbol']:
                                self.tree.item(item, values=(r['symbol'], f"${r['price']:.2f}", f"{r['rsi']:.0f}", display_status), tags=(tag,))
                                found = True; break
                        if not found: self.tree.insert("", "end", values=(r['symbol'], f"${r['price']:.2f}", f"{r['rsi']:.0f}", display_status), tags=(tag,))
                        if r['symbol'] == self.selected_symbol: self.render_chart(r)
                elif mtype == 'portfolio':
                    self.lbl_cap.configure(text=f"Saldo: ${data['available_capital']:.2f}")
                    pnl = data['floating_pnl']
                    self.lbl_pnl.configure(text=f"PnL Aberto: ${pnl:.2f}", text_color="#2ecc71" if pnl>=0 else "#e74c3c")
                elif mtype == 'trade_history':
                    for i in self.tree_hist.get_children(): self.tree_hist.delete(i)
                    for r in data: self.tree_hist.insert("", "end", values=(r[0], f"${r[1]:.2f}"))
                elif mtype == 'log':
                    self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] > {data}\n"); self.log_box.see("end")
        except: pass
        self.root.after(100, self.process_queue)

    def render_chart(self, data):
        self.ax.clear()
        df = data['df'].tail(60)
        mc = mpf.make_marketcolors(up='#00ff88', down='#ff3333', inherit=True)
        s = mpf.make_mpf_style(base_mpl_style='dark_background', marketcolors=mc, facecolor='#0e0e0e')
        add_plots = [
            mpf.make_addplot(df['upper_bb'], color='#3498db', width=0.7, ax=self.ax),
            mpf.make_addplot(df['lower_bb'], color='#3498db', width=0.7, ax=self.ax),
            mpf.make_addplot(df['ma20'], color='#f1c40f', width=0.8, ax=self.ax)
        ]
        
        # --- VISUALIZAÇÃO DA EMA 200 ---
        if 'ema200' in df.columns and not df['ema200'].isnull().all():
            add_plots.append(mpf.make_addplot(df['ema200'], color='orange', width=1.5, ax=self.ax))
            
        if data.get('trade_info'):
            entry = data['trade_info']['entry']
            add_plots.append(mpf.make_addplot([entry]*len(df), color='#2ecc71', width=1.5, linestyle='--', ax=self.ax))
            self.ax.text(df.index[5], entry, f" COMPRA: ${entry:.2f}", color='#2ecc71', fontweight='bold', bbox=dict(facecolor='black', alpha=0.6))
        
        curr_rsi = df['rsi'].iloc[-1]
        self.ax.text(0.02, 0.95, f"RSI: {curr_rsi:.1f}", transform=self.ax.transAxes, color='white', weight='bold', bbox=dict(facecolor='black', alpha=0.7))
        mpf.plot(df, type='candle', ax=self.ax, style=s, addplot=add_plots)
        self.ax.set_title(f"MONITORANDO: {data['symbol']}", color="#00ffcc", loc='left')
        self.canvas.draw_idle()

    def start_bot(self): asyncio.run_coroutine_threadsafe(self.engine.start(), self.loop)
    def stop_bot(self): asyncio.run_coroutine_threadsafe(self.engine.stop(), self.loop)
    def panic_bot(self): asyncio.run_coroutine_threadsafe(self.engine.emergency_close_all(), self.loop)

    def on_closing(self):
        print("🛑 Encerrando sistema de forma segura...")
        # 1. Para o Motor
        self.engine.running = False
        
        # 2. Para o loop do asyncio
        self.loop.call_soon_threadsafe(self.loop.stop())
        
        # 3. Fecha a janela
        self.root.destroy()
        # Força a saída do processo caso threads ainda existam
        os._exit(0)

    def run(self): self.root.mainloop()