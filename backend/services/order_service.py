import logging
import asyncio
from typing import Optional
from datetime import datetime

from .fyers_service import FyersService
from database.models import AsyncSessionLocal
from database.operations import TradeRepo, ReentryRepo, DailyPnLRepo, LogRepo

logger = logging.getLogger(__name__)

# Global set to prevent duplicate orders
_pending_orders: set = set()


class OrderService:
    """Handles order execution, deduplication, and trade recording."""

    def __init__(self, fyers: FyersService, lot_size: int = 50):
        self.fyers = fyers
        self.lot_size = lot_size

    async def sell_option(self, symbol: str, leg: str, qty: int, 
                           reentry_count: int = 0) -> Optional[dict]:
        """Place a SELL order for an option."""
        key = f"ENTRY_{symbol}_{qty}"
        if key in _pending_orders:
            logger.warning(f"Duplicate order prevented: {key}")
            return None

        _pending_orders.add(key)
        try:
            result = await self.fyers.place_order_with_retry(
                symbol=symbol,
                qty=qty,
                side=-1,  # SELL
                order_type=2  # Market
            )
            
            if result.get("s") != "ok":
                logger.error(f"Order failed: {result}")
                return None

            fyers_order_id = result.get("id", "")
            fill_price = result.get("tradedPrice", 0)

            async with AsyncSessionLocal() as db:
                repo = TradeRepo(db)
                trade = await repo.create(
                    symbol=symbol,
                    leg=leg,
                    entry_time=datetime.now(),
                    qty=qty,
                    entry_price=fill_price,
                    reentry_count=reentry_count,
                    fyers_order_id=fyers_order_id,
                    status="OPEN"
                )
                
                log_repo = LogRepo(db)
                await log_repo.log("INFO", f"{leg} ENTRY", {
                    "symbol": symbol, "qty": qty, "price": fill_price
                })

            return {"trade_id": trade.id, "fill_price": fill_price, "order_id": fyers_order_id}

        except Exception as e:
            logger.error(f"Order execution error: {e}")
            return None
        finally:
            _pending_orders.discard(key)

    async def exit_option(self, trade_id: int, symbol: str, leg: str, 
                           qty: int, exit_reason: str) -> Optional[dict]:
        """Exit an open trade (BUY to cover SELL)."""
        key = f"EXIT_{trade_id}"
        if key in _pending_orders:
            logger.warning(f"Duplicate exit prevented: {key}")
            return None

        _pending_orders.add(key)
        try:
            result = await self.fyers.place_order_with_retry(
                symbol=symbol,
                qty=qty,
                side=1,  # BUY to exit
                order_type=2
            )

            if result.get("s") != "ok":
                logger.error(f"Exit order failed: {result}")
                return None

            fill_price = result.get("tradedPrice", 0)

            async with AsyncSessionLocal() as db:
                repo = TradeRepo(db)
                trade = await repo.close_trade(trade_id, fill_price, exit_reason)
                
                pnl = trade.pnl if trade else 0
                result_str = "WIN" if pnl >= 0 else "LOSS"
                
                pnl_repo = DailyPnLRepo(db)
                await pnl_repo.upsert_today(pnl, result_str)
                
                log_repo = LogRepo(db)
                await log_repo.log("INFO", f"{leg} EXIT", {
                    "symbol": symbol, "qty": qty,
                    "price": fill_price, "reason": exit_reason, "pnl": pnl
                })

                if exit_reason == "SL":
                    reentry_repo = ReentryRepo(db)
                    await reentry_repo.increment(leg)

            return {"fill_price": fill_price, "pnl": pnl}

        except Exception as e:
            logger.error(f"Exit error: {e}")
            return None
        finally:
            _pending_orders.discard(key)

    async def force_exit_all(self, open_trades: list):
        """Force exit all open positions at 3:15 PM."""
        tasks = []
        for trade in open_trades:
            tasks.append(self.exit_option(
                trade.id, trade.symbol, trade.leg,
                trade.qty, "FORCE"
            ))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
