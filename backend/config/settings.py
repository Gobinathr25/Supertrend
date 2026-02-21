import os
from pydantic_settings import BaseSettings
from pydantic import model_validator


class Settings(BaseSettings):
    SECRET_KEY: str = "supersecretkey"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    MAX_DAILY_LOSS: float = 10000.0
    MAX_TRADES_PER_DAY: int = 20
    LOT_SIZE: int = 50
    SCALING_ENABLED: bool = True
    ST_PERIOD: int = 10
    ST_MULTIPLIER: float = 3.0
    MARKET_OPEN: str = "09:15"
    LAST_ENTRY: str = "14:45"
    FORCE_EXIT: str = "15:15"

    model_config = {
        "extra": "allow",
    }


settings = Settings()
