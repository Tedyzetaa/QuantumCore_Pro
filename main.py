import customtkinter as ctk
from interface.main_window import MultiPairTradingInterface
from core.engine import TradingEngine
from core.config import Config
import queue, threading, asyncio

if __name__ == "__main__":
    root = ctk.CTk()
    app = MultiPairTradingInterface(root, TradingEngine, Config)
    app.run()