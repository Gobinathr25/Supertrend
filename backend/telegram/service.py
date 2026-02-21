import logging
import httpx
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TelegramService:
    BASE_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, bot_token: str = "", chat_id: str = ""):
        self.bot_token = bot_token
        self.chat_id = chat_id

    def configure(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id

    async def send(self, message: str) -> bool:
        if not self.bot_token or not self.chat_id:
            return False
        url = self.BASE_URL.format(token=self.bot_token)
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(url, json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }, timeout=10)
                return r.status_code == 200
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    async def test_connection(self) -> bool:
        return await self.send("✅ <b>Trading Bot Connected</b>\nConnection test successful.")

    async def notify_entry(self, symbol: str, qty: int, price: float, leg: str):
        msg = (
            f"📥 <b>ORDER PLACED</b>\n"
            f"Symbol: <code>{symbol}</code>\n"
            f"Action: SELL {leg}\n"
            f"Qty: {qty}\n"
            f"Price: ₹{price:.2f}\n"
            f"Time: {datetime.now().strftime('%H:%M:%S')}"
        )
        await self.send(msg)

    async def notify_exit(self, symbol: str, qty: int, price: float, pnl: float, reason: str, leg: str):
        emoji = "🟢" if pnl >= 0 else "🔴"
        msg = (
            f"{emoji} <b>ORDER EXITED</b>\n"
            f"Symbol: <code>{symbol}</code>\n"
            f"Exit Price: ₹{price:.2f}\n"
            f"Qty: {qty}\n"
            f"PnL: ₹{pnl:+.2f}\n"
            f"Reason: {reason}\n"
            f"Time: {datetime.now().strftime('%H:%M:%S')}"
        )
        await self.send(msg)

    async def notify_sl(self, symbol: str, exit_price: float, pnl: float, leg: str):
        msg = (
            f"🛑 <b>SL HIT</b>\n"
            f"NIFTY {leg} SL HIT\n"
            f"Exit Price: ₹{exit_price:.2f}\n"
            f"PnL: ₹{pnl:+.2f}"
        )
        await self.send(msg)

    async def notify_reentry(self, symbol: str, qty: int, price: float, count: int, leg: str):
        msg = (
            f"🔄 <b>RE-ENTRY #{count}</b>\n"
            f"Symbol: <code>{symbol}</code>\n"
            f"Qty: {qty} ({count}X)\n"
            f"Price: ₹{price:.2f}"
        )
        await self.send(msg)

    async def send_daily_summary(self, pnl: float, trades: int, win: int, loss: int):
        emoji = "🟢" if pnl >= 0 else "🔴"
        msg = (
            f"{emoji} <b>DAILY SUMMARY - {datetime.now().strftime('%d %b %Y')}</b>\n"
            f"Total PnL: ₹{pnl:+.2f}\n"
            f"Total Trades: {trades}\n"
            f"Winning: {win} | Losing: {loss}\n"
            f"Win Rate: {(win/trades*100):.1f}%" if trades > 0 else "No trades today"
        )
        await self.send(msg)
