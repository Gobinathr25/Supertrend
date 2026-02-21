from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    SECRET_KEY: str = "supersecretkey_change_in_production"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    
    # Trading defaults
    MAX_DAILY_LOSS: float = 10000.0
    MAX_TRADES_PER_DAY: int = 20
    LOT_SIZE: int = 50
    SCALING_ENABLED: bool = True
    
    # Supertrend
    ST_PERIOD: int = 10
    ST_MULTIPLIER: float = 3.0
    
    # Market hours
    MARKET_OPEN: str = "09:15"
    LAST_ENTRY: str = "14:45"
    FORCE_EXIT: str = "15:15"
    
    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
