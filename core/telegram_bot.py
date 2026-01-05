import asyncio
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
import sqlite3
import time

class TelegramManager:
    def __init__(self, token, chat_id, engine=None):
        self.token = token
        self.chat_id = chat_id
        self.engine = engine
        self.application = Application.builder().token(token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.menu_principal))
        self.application.add_handler(CommandHandler("status", self.status_comando))
        self.application.add_handler(CallbackQueryHandler(self.handle_buttons))

    async def menu_principal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("📊 Relatório Detalhado", callback_data='rel_detalhado')],
            [InlineKeyboardButton("📉 Resumo de Hoje", callback_data='rel_resumo')],
            [InlineKeyboardButton("🔄 Status das Máquinas", callback_data='status_engine')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🤖 **QuantumCore Command Center**\nEscolha uma opção:", 
                                      reply_markup=reply_markup, parse_mode='Markdown')

    async def handle_buttons(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == 'rel_detalhado':
            msg = self._get_detailed_report()
            await query.edit_message_text(msg, parse_mode='Markdown')
        elif query.data == 'rel_resumo':
            msg = self._get_summary_report()
            await query.edit_message_text(msg, parse_mode='Markdown')

    def _get_detailed_report(self):
        conn = sqlite3.connect('trades_history.db')
        trades = conn.execute("SELECT symbol, side, price, pnl, timestamp FROM trades ORDER BY id DESC LIMIT 5").fetchall()
        conn.close()
        
        if not trades: return "📭 Nenhum trade registrado ainda."
        
        report = "📑 **ÚLTIMOS TRADES DETALHADOS**\n\n"
        for t in trades:
            emoji = "🟢" if t[1] == 'BUY' else "🔴"
            pnl_str = f"| PnL: *${t[3]:.2f}*" if t[3] else ""
            report += f"{emoji} **{t[0]}**\n   Preço: ${t[2]:.4f} {pnl_str}\n   Data: {t[4][:16]}\n\n"
        return report

    def _get_summary_report(self):
        conn = sqlite3.connect('trades_history.db')
        res = conn.execute("SELECT COUNT(*), SUM(pnl) FROM trades WHERE side='SELL'").fetchone()
        conn.close()
        
        count = res[0] or 0
        total_pnl = res[1] or 0.0
        color = "📈" if total_pnl >= 0 else "📉"
        
        return f"📊 **RESUMO DE PERFORMANCE**\n\n✅ Total de Vendas: {count}\n{color} PnL Acumulado: *${total_pnl:.2f}*\n💰 Ticket Médio: *${(total_pnl/count if count > 0 else 0):.2f}*"

    async def status_comando(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        conn = sqlite3.connect('trades_history.db')
        # Pega o PnL total apenas de hoje
        hoje = time.strftime('%Y-%m-%d')
        res = conn.execute(f"SELECT COUNT(*), SUM(pnl) FROM trades WHERE side='SELL' AND timestamp LIKE '{hoje}%'").fetchone()
        conn.close()
        
        count = res[0] or 0
        total_pnl = res[1] or 0.0
        
        msg = f"🤖 **STATUS ATUAL**\n\n✅ Trades Hoje: {count}\n💵 PnL Hoje: *${total_pnl:.2f}*\n🔋 Slots: {len(self.engine.active_trades)}/2"
        await update.message.reply_text(msg, parse_mode='Markdown')

    async def send_notification(self, text):
        try:
            bot = Bot(token=self.token)
            await bot.send_message(chat_id=self.chat_id, text=text, parse_mode='Markdown')
        except Exception as e:
            print(f"Erro Telegram: {e}")

    async def start(self):
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()