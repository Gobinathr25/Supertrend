import logging
import asyncio
import json
import time
from typing import Optional, Callable, Dict, Any
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


class FyersService:
    """
    Fyers API v3 wrapper.
    All credentials are passed at runtime (no hardcoding).
    """
    BASE_URL = "https://api-t1.fyers.in/api/v3"
    AUTH_URL = "https://api-t2.fyers.in/vagator/v2"
    DATA_URL = "https://api-t1.fyers.in/data"

    def __init__(self):
        self.client_id: Optional[str] = None
        self.secret_key: Optional[str] = None
        self.access_token: Optional[str] = None
        self._ws = None
        self._ws_callbacks: list[Callable] = []
        self._ws_running = False

    def configure(self, client_id: str, secret_key: str, access_token: str):
        self.client_id = client_id
        self.secret_key = secret_key
        self.access_token = access_token

    def _headers(self) -> dict:
        return {
            "Authorization": f"{self.client_id}:{self.access_token}",
            "Content-Type": "application/json"
        }

    async def validate_token(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{self.BASE_URL}/profile", headers=self._headers(), timeout=10)
                return r.status_code == 200
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            return False

    async def get_profile(self) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.BASE_URL}/profile", headers=self._headers(), timeout=10)
            r.raise_for_status()
            return r.json()

    async def get_funds(self) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.BASE_URL}/funds", headers=self._headers(), timeout=10)
            r.raise_for_status()
            return r.json()

    async def get_quotes(self, symbols: list[str]) -> dict:
        """Get live quotes for a list of symbols."""
        sym_str = ",".join(symbols)
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.DATA_URL}/quotes",
                params={"symbols": sym_str},
                headers=self._headers(),
                timeout=10
            )
            r.raise_for_status()
            return r.json()

    async def get_positions(self) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.BASE_URL}/positions", headers=self._headers(), timeout=10)
            r.raise_for_status()
            return r.json()

    async def get_orders(self) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.BASE_URL}/orders", headers=self._headers(), timeout=10)
            r.raise_for_status()
            return r.json()

    async def place_order(self, symbol: str, qty: int, side: int,
                          order_type: int = 2, product_type: str = "INTRADAY",
                          limit_price: float = 0) -> dict:
        """
        side: -1 = SELL, 1 = BUY
        order_type: 1=Limit, 2=Market
        """
        payload = {
            "symbol": symbol,
            "qty": qty,
            "type": order_type,
            "side": side,
            "productType": product_type,
            "limitPrice": limit_price,
            "stopPrice": 0,
            "validity": "DAY",
            "disclosedQty": 0,
            "offlineOrder": False
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.BASE_URL}/orders/sync",
                json=payload,
                headers=self._headers(),
                timeout=15
            )
            r.raise_for_status()
            return r.json()

    async def place_order_with_retry(self, **kwargs) -> dict:
        """Retry up to 3 times on failure."""
        for attempt in range(3):
            try:
                return await self.place_order(**kwargs)
            except Exception as e:
                logger.warning(f"Order attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(1)
        raise Exception("Order placement failed after 3 retries")

    async def exit_position(self, symbol: str) -> dict:
        """Exit a specific position."""
        payload = {"id": symbol, "type": 1}
        async with httpx.AsyncClient() as client:
            r = await client.delete(
                f"{self.BASE_URL}/positions",
                json=payload,
                headers=self._headers(),
                timeout=15
            )
            r.raise_for_status()
            return r.json()

    async def get_margin_required(self, symbol: str, qty: int, side: int) -> float:
        """Get required margin for a trade."""
        payload = {
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "type": 2,
            "productType": "INTRADAY"
        }
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{self.BASE_URL}/orders/margin",
                    json=payload,
                    headers=self._headers(),
                    timeout=10
                )
                data = r.json()
                return data.get("marginRequired", 0)
        except Exception:
            return 0

    async def get_historical_data(self, symbol: str, resolution: str, 
                                   date_format: str, range_from: str, range_to: str) -> dict:
        params = {
            "symbol": symbol,
            "resolution": resolution,
            "date_format": date_format,
            "range_from": range_from,
            "range_to": range_to,
            "cont_flag": "1"
        }
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.DATA_URL}/history",
                params=params,
                headers=self._headers(),
                timeout=30
            )
            r.raise_for_status()
            return r.json()

    def add_ws_callback(self, callback: Callable):
        self._ws_callbacks.append(callback)

    async def start_websocket(self, symbols: list[str]):
        """Start Fyers WebSocket for live data."""
        import websockets
        
        self._ws_running = True
        ws_url = f"wss://api-t2.fyers.in/socket/v3/dataSock?type=symbolData&user-agent=fyers-api&Authorization={self.client_id}:{self.access_token}"
        
        subscribe_msg = {
            "T": "SUB_L2",
            "TLIST": symbols,
            "SUB_T": 1
        }

        while self._ws_running:
            try:
                async with websockets.connect(ws_url, ping_interval=30) as ws:
                    await ws.send(json.dumps(subscribe_msg))
                    logger.info("WebSocket connected, subscribed to symbols.")
                    
                    async for message in ws:
                        if not self._ws_running:
                            break
                        try:
                            data = json.loads(message)
                            for cb in self._ws_callbacks:
                                asyncio.create_task(cb(data))
                        except json.JSONDecodeError:
                            pass
            except Exception as e:
                logger.error(f"WebSocket error: {e}, reconnecting in 5s...")
                if self._ws_running:
                    await asyncio.sleep(5)

    def stop_websocket(self):
        self._ws_running = False


class ATMCalculator:
    """Calculate ATM strike and option symbols."""
    
    @staticmethod
    def get_atm_strike(spot: float, step: int = 50) -> int:
        return round(spot / step) * step

    @staticmethod
    def get_option_symbol(index: str, strike: int, expiry: str, opt_type: str) -> str:
        """
        Build Fyers option symbol.
        Example: NSE:NIFTY25JAN24500CE
        expiry format: DDMMMYY e.g. 25JAN24
        """
        return f"NSE:{index}{expiry}{strike}{opt_type}"

    @staticmethod
    def get_nearest_expiry_str() -> str:
        """Returns nearest weekly expiry string in DDMMMYY format."""
        from datetime import date, timedelta
        today = date.today()
        # NIFTY weekly expiry is Thursday
        days_to_thursday = (3 - today.weekday()) % 7
        if days_to_thursday == 0 and today.weekday() == 3:
            days_to_thursday = 0
        expiry = today + timedelta(days=days_to_thursday)
        return expiry.strftime("%d%b%y").upper()
