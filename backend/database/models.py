from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
from sqlalchemy import String, Float, Integer, DateTime, Boolean, Text, JSON
from datetime import datetime
from typing import Optional
import os

# DB path resolution:
# 1. Use DATABASE_PATH env var if set
# 2. Use /data/trading.db if /data directory exists (Render persistent disk)
# 3. Fall back to local trading.db next to the backend folder
def _resolve_db_path():
    env_path = os.environ.get("DATABASE_PATH")
    if env_path:
        os.makedirs(os.path.dirname(os.path.abspath(env_path)), exist_ok=True)
        return env_path
    data_dir = "/data"
    if os.path.isdir(data_dir):
        return os.path.join(data_dir, "trading.db")
    local = os.path.join(os.path.dirname(__file__), "..", "trading.db")
    return os.path.abspath(local)

DB_PATH = _resolve_db_path()
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Trade(Base):
    __tablename__ = "trades"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    symbol: Mapped[str] = mapped_column(String(50))
    leg: Mapped[str] = mapped_column(String(10))  # CE or PE
    entry_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    exit_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    qty: Mapped[int] = mapped_column(Integer)
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # SL, TARGET, FORCE, MANUAL
    reentry_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="OPEN")  # OPEN, CLOSED
    order_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    fyers_order_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)


class DailyPnL(Base):
    __tablename__ = "daily_pnl"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime] = mapped_column(DateTime, unique=True)
    total_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    winning_trades: Mapped[int] = mapped_column(Integer, default=0)
    losing_trades: Mapped[int] = mapped_column(Integer, default=0)
    max_drawdown: Mapped[float] = mapped_column(Float, default=0.0)


class StrategyLog(Base):
    __tablename__ = "strategy_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    level: Mapped[str] = mapped_column(String(10))  # INFO, WARN, ERROR
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class ReentryTracking(Base):
    __tablename__ = "reentry_tracking"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime] = mapped_column(DateTime)
    leg: Mapped[str] = mapped_column(String(10))
    reentry_count: Mapped[int] = mapped_column(Integer, default=0)
    is_stopped: Mapped[bool] = mapped_column(Boolean, default=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AppConfig(Base):
    __tablename__ = "app_config"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
