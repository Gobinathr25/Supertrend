from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_
from datetime import datetime, date
from typing import Optional, List
from .models import Trade, DailyPnL, StrategyLog, ReentryTracking, AppConfig


class TradeRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **kwargs) -> Trade:
        trade = Trade(**kwargs)
        self.db.add(trade)
        await self.db.commit()
        await self.db.refresh(trade)
        return trade

    async def get_open_trades(self) -> List[Trade]:
        result = await self.db.execute(select(Trade).where(Trade.status == "OPEN"))
        return result.scalars().all()

    async def get_open_by_leg(self, leg: str) -> Optional[Trade]:
        result = await self.db.execute(
            select(Trade).where(and_(Trade.status == "OPEN", Trade.leg == leg))
        )
        return result.scalar_one_or_none()

    async def close_trade(self, trade_id: int, exit_price: float, exit_reason: str):
        trade = await self.db.get(Trade, trade_id)
        if trade:
            trade.exit_price = exit_price
            trade.exit_time = datetime.now()
            trade.exit_reason = exit_reason
            trade.pnl = (trade.entry_price - exit_price) * trade.qty  # SELL trade
            trade.status = "CLOSED"
            await self.db.commit()
            return trade
        return None

    async def get_today_trades(self) -> List[Trade]:
        today = date.today()
        result = await self.db.execute(
            select(Trade).where(
                func.date(Trade.entry_time) == today
            )
        )
        return result.scalars().all()

    async def get_all_trades(self) -> List[Trade]:
        result = await self.db.execute(select(Trade).order_by(Trade.entry_time.desc()))
        return result.scalars().all()


class ReentryRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_today(self, leg: str) -> Optional[ReentryTracking]:
        today = date.today()
        result = await self.db.execute(
            select(ReentryTracking).where(
                and_(
                    func.date(ReentryTracking.date) == today,
                    ReentryTracking.leg == leg
                )
            )
        )
        return result.scalar_one_or_none()

    async def increment(self, leg: str) -> ReentryTracking:
        record = await self.get_today(leg)
        if not record:
            record = ReentryTracking(date=datetime.now(), leg=leg, reentry_count=1)
            self.db.add(record)
        else:
            record.reentry_count += 1
            record.last_updated = datetime.now()
            if record.reentry_count >= 3:
                record.is_stopped = True
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def is_stopped(self, leg: str) -> bool:
        record = await self.get_today(leg)
        if not record:
            return False
        return record.is_stopped

    async def get_count(self, leg: str) -> int:
        record = await self.get_today(leg)
        return record.reentry_count if record else 0


class ConfigRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, key: str) -> Optional[str]:
        result = await self.db.execute(select(AppConfig).where(AppConfig.key == key))
        record = result.scalar_one_or_none()
        return record.value if record else None

    async def set(self, key: str, value: str):
        result = await self.db.execute(select(AppConfig).where(AppConfig.key == key))
        record = result.scalar_one_or_none()
        if record:
            record.value = value
            record.updated_at = datetime.now()
        else:
            record = AppConfig(key=key, value=value)
            self.db.add(record)
        await self.db.commit()

    async def get_all(self) -> dict:
        result = await self.db.execute(select(AppConfig))
        records = result.scalars().all()
        return {r.key: r.value for r in records}


class DailyPnLRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert_today(self, pnl_delta: float, trade_result: str):
        today = date.today()
        result = await self.db.execute(
            select(DailyPnL).where(func.date(DailyPnL.date) == today)
        )
        record = result.scalar_one_or_none()
        if not record:
            record = DailyPnL(date=datetime.now(), total_pnl=0, total_trades=0)
            self.db.add(record)
        record.total_pnl += pnl_delta
        record.total_trades += 1
        if trade_result == "WIN":
            record.winning_trades += 1
        else:
            record.losing_trades += 1
        await self.db.commit()

    async def get_all(self) -> List[DailyPnL]:
        result = await self.db.execute(select(DailyPnL).order_by(DailyPnL.date.desc()))
        return result.scalars().all()


class LogRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(self, level: str, message: str, data: dict = None):
        log = StrategyLog(level=level, message=message, data=data)
        self.db.add(log)
        await self.db.commit()
