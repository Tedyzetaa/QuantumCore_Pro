import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
import mplfinance as mpf
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import queue, threading, asyncio, time

class MultiPairTradingInterface:
    def __init__(self, root, engine_class, config):
        self.root = root
        self.config = config
        self.update_queue = queue.Queue()
        self.engine = engine_class(self.update_queue, self.config)
        self.loop = asyncio.new_event_loop()
        
        self.selected_symbol = self.config.PAIRS[0]['symbol']
        self.cached_dfs = {}
        
        self.fig, self.ax = plt.subplots(figsize=(8, 5), dpi=100)
        self.fig.patch.set_facecolor('#0e0e0e')
        self.ax.set_facecolor('#0e0e0e')
        
        self.setup_ui()
        self.root.after(100, self.process_queue)
        threading.Thread(target=self._run_async_loop, daemon=True).start()

    def _run_async_loop(self):
        asyncio.set_event_loop(self.loop)
        while True:
            try:
                self.loop.run_until_complete(self.engine.trading_cycle())
                time.sleep(1)
            except: pass

    def setup_ui(self):
        self.root.title("QuantumCore v37.0 - Flexible Terminal")
        self.root.geometry("1450x900")
        
        # --- PANED WINDOW PRINCIPAL (Horizontal) ---
        self.main_pane = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg="#0a0a0a", sashwidth=4, sashrelief=tk.RAISED)
        self.main_pane.pack(fill="both", expand=True)

        # SIDEBAR (Lado Esquerdo)
        self.sidebar = ctk.CTkFrame(self.main_pane, corner_radius=0, fg_color="#121212")
        self.main_pane.add(self.sidebar, width=350)

        # --- INFORMAÇÕES DA CONTA (PNL / SALDO) ---
        self.fin_frame = ctk.CTkFrame(self.sidebar, fg_color="#1e1e1e", corner_radius=10)
        self.fin_frame.pack(pady=10, padx=10, fill="x")

        self.lbl_cap = ctk.CTkLabel(self.fin_frame, text="Saldo: $0.00", font=("Arial", 18, "bold"), text_color="#00ffcc")
        self.lbl_cap.pack(pady=5)

        self.lbl_pnl = ctk.CTkLabel(self.fin_frame, text="PnL Aberto: $0.00", font=("Arial", 14), text_color="gray")
        self.lbl_pnl.pack(pady=5)

        ctk.CTkLabel(self.sidebar, text="TRADING CORE", font=("Impact", 24), text_color="#00ffcc").pack(pady=(10, 15))

        # Botões Principais
        self.btn_start = ctk.CTkButton(self.sidebar, text="▶ START", fg_color="#2ecc71", command=self.start_bot)
        self.btn_start.pack(pady=5, padx=20, fill="x")
        self.btn_stop = ctk.CTkButton(self.sidebar, text="⏸ STOP", fg_color="#e67e22", command=self.stop_bot)
        self.btn_stop.pack(pady=5, padx=20, fill="x")
        self.btn_panic = ctk.CTkButton(self.sidebar, text="🚨 PÂNICO", fg_color="#c0392b", command=self.panic_bot)
        self.btn_panic.pack(pady=15, padx=20, fill="x")

        # Tabela Mercado
        ctk.CTkLabel(self.sidebar, text="MERCADO ATIVO", font=("Arial", 11, "bold"), text_color="gray").pack(pady=(10,0))
        self.tree_pairs = ttk.Treeview(self.sidebar, columns=("P", "Pr", "R", "S"), show="headings", height=15)
        self.tree_pairs.heading("P", text="PAR")
        self.tree_pairs.heading("Pr", text="PREÇO")
        self.tree_pairs.heading("R", text="RSI")
        self.tree_pairs.heading("S", text="STATUS")
        
        self.tree_pairs.column("P", width=80)
        self.tree_pairs.column("Pr", width=80)
        self.tree_pairs.column("R", width=40)
        self.tree_pairs.column("S", width=100)
        self.tree_pairs.pack(pady=5, padx=10, fill="x")

        # --- DEFINIÇÃO DE CORES DOS STATUS ---
        self.tree_pairs.tag_configure('neutral', foreground='gray')
        self.tree_pairs.tag_configure('buy_signal', background='#27ae60', foreground='white') # Verde
        self.tree_pairs.tag_configure('bought', background='#2980b9', foreground='white')   # Azul
        self.tree_pairs.tag_configure('selling', background='#e67e22', foreground='white')  # Laranja/Alerta
        
        self.tree_pairs.bind("<<TreeviewSelect>>", self.on_select)

        # Histórico
        ctk.CTkLabel(self.sidebar, text="VENDAS RECENTES", font=("Arial", 11, "bold"), text_color="gray").pack(pady=(15,0))
        self.tree_hist = ttk.Treeview(self.sidebar, columns=("H_P", "H_PnL"), show="headings", height=6)
        self.tree_hist.heading("H_P", text="PAR"); self.tree_hist.heading("H_PnL", text="PNL")
        self.tree_hist.column("H_P", width=110); self.tree_hist.column("H_PnL", width=110)
        self.tree_hist.pack(pady=5, padx=10, fill="both", expand=True)

        # --- ÁREA DIREITA (Gráfico e Log) ---
        self.right_pane = tk.PanedWindow(self.main_pane, orient=tk.VERTICAL, bg="#0a0a0a", sashwidth=4, sashrelief=tk.RAISED)
        self.main_pane.add(self.right_pane)

        # Área do Gráfico
        self.chart_container = ctk.CTkFrame(self.right_pane, fg_color="#0e0e0e")
        self.right_pane.add(self.chart_container, height=600)

        # Seletores de Tempo
        self.time_frame = ctk.CTkFrame(self.chart_container, fg_color="transparent")
        self.time_frame.pack(fill="x", padx=20, pady=(10,0))
        for t in ["1m", "5m", "15m", "1h"]:
            ctk.CTkButton(self.time_frame, text=t, width=50, fg_color="#1e1e1e", command=lambda x=t: self.log(f"Timeframe {x} selecionado (Visual)")).pack(side="left", padx=5)

        self.chart_area = ctk.CTkFrame(self.chart_container, fg_color="#0e0e0e", corner_radius=15)
        self.chart_area.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.chart_area)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

        # Área de Log
        self.log_container = ctk.CTkFrame(self.right_pane, fg_color="#0e0e0e")
        self.right_pane.add(self.log_container, height=200)

        self.log_box = ctk.CTkTextbox(self.log_container, fg_color="#0e0e0e", text_color="#00ff88", font=("Consolas", 11))
        self.log_box.pack(fill="both", expand=True, padx=20, pady=20)

    def on_select(self, event):
        sel = self.tree_pairs.selection()
        if sel:
            symbol = self.tree_pairs.item(sel[0], "values")[0]
            self.selected_symbol = symbol
            if symbol in self.cached_dfs: self.render_chart({'symbol': symbol, 'df': self.cached_dfs[symbol]})

    def sort_col(self, col):
        l = [(self.tree_pairs.set(k, col), k) for k in self.tree_pairs.get_children('')]
        l.sort(reverse=True)
        for index, (val, k) in enumerate(l): self.tree_pairs.move(k, '', index)

    def process_queue(self):
        try:
            while not self.update_queue.empty():
                mtype, data = self.update_queue.get_nowait()
                if mtype == 'pairs_data':
                    # Atualiza tabela e cache
                    for r in data:
                        self.cached_dfs[r['symbol']] = r['df']
                        
                        symbol = r['symbol']
                        status = r['status']
                        
                        vals = (symbol, f"${r['price']:.2f}", f"{r['rsi']:.0f}", status)
                        
                        # Define a tag baseada no texto do status
                        tag = 'neutral'
                        if "COMPRA" in status: tag = 'buy_signal'
                        elif "COMPRADO" in status or "PROTEGIDO" in status: tag = 'bought'
                        elif "VENDENDO" in status: tag = 'selling'
                        
                        # Atualiza ou insere na tree
                        found = False
                        for item in self.tree_pairs.get_children():
                            if self.tree_pairs.item(item, 'values')[0] == symbol:
                                self.tree_pairs.item(item, values=vals, tags=(tag,))
                                found = True; break
                        if not found: self.tree_pairs.insert("", "end", values=vals, tags=(tag,))
                        
                        if r['symbol'] == self.selected_symbol: self.render_chart(r)
                elif mtype == 'trade_history':
                    for i in self.tree_hist.get_children(): self.tree_hist.delete(i)
                    for r in data: self.tree_hist.insert("", "end", values=(r[0], f"${r[1]:.2f}"))
                elif mtype == 'log':
                    self.log_box.insert("end", f"> {data}\n"); self.log_box.see("end")
                elif mtype == 'portfolio':
                    self.lbl_cap.configure(text=f"Saldo: ${data['available_capital']:.2f}")
                    pnl_color = "#2ecc71" if data['floating_pnl'] >= 0 else "#e74c3c"
                    self.lbl_pnl.configure(text=f"PnL Aberto: ${data['floating_pnl']:.2f}", text_color=pnl_color)
        except: pass
        self.root.after(100, self.process_queue)

    def render_chart(self, data):
        self.ax.clear()
        df = data['df'].tail(50)
        mc = mpf.make_marketcolors(up='#00ff88', down='#ff3333', inherit=True)
        s = mpf.make_mpf_style(base_mpl_style='dark_background', marketcolors=mc, facecolor='#0e0e0e')
        mpf.plot(df, type='candle', ax=self.ax, style=s)
        self.ax.set_title(f"LIVE: {data['symbol']}", color="#00ffcc", loc='left')
        self.canvas.draw_idle()

    def start_bot(self): asyncio.run_coroutine_threadsafe(self.engine.start(), self.loop)
    def stop_bot(self): asyncio.run_coroutine_threadsafe(self.engine.stop(), self.loop)
    def panic_bot(self): asyncio.run_coroutine_threadsafe(self.engine.emergency_close_all(), self.loop)
    def log(self, m): self.update_queue.put(('log', m))
    def run(self): self.root.mainloop()