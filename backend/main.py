import asyncio
import logging
import sys
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.dirname(__file__))

from database.models import init_db, get_db, AsyncSessionLocal
from database.operations import TradeRepo, DailyPnLRepo, ConfigRepo, LogRepo
from services.orchestrator import orchestrator
from services.fyers_auth import FyersAuth, start_local_callback_server, stop_local_callback_server
from notifications.service import TelegramService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Auth state ────────────────────────────────────────────────────────────────
_auth_in_progress = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialised.")
    yield
    orchestrator.stop()
    stop_local_callback_server()


app = FastAPI(title="NIFTY Options Trading Bot", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


# ── Models ────────────────────────────────────────────────────────────────────

class BrokerCredentials(BaseModel):
    app_id: str
    secret_id: str
    redirect_uri: str = ""   # optional — leave blank to use localhost:8765

class TelegramConfig(BaseModel):
    telegram_token: str = ""
    telegram_chat_id: str = ""

class RiskSettingsRequest(BaseModel):
    max_daily_loss: float
    max_trades_per_day: int
    lot_size: int
    scaling_enabled: bool

class StartTradingRequest(BaseModel):
    lot_size: int = 50
    max_daily_loss: float = 10000
    max_trades: int = 20
    scaling_enabled: bool = True
    trade_mode: str = "real"          # "real" or "paper"
    nifty_enabled: bool = True
    sensex_enabled: bool = False


# ══════════════════════════════════════════════════════════════════════════════
# AUTH FLOW — Fully automatic via local callback server
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/auth/save-broker")
async def save_broker(req: BrokerCredentials, db: AsyncSession = Depends(get_db)):
    repo = ConfigRepo(db)
    await repo.set("app_id",    req.app_id)
    await repo.set("secret_id", req.secret_id)
    if req.redirect_uri:
        await repo.set("redirect_uri", req.redirect_uri.rstrip("/"))
    await repo.set("access_token", "")
    await repo.set("auth_status", "credentials_saved")
    return {"status": "saved"}


@app.post("/api/auth/initiate-login")
async def initiate_login(db: AsyncSession = Depends(get_db)):
    """
    Start the local callback server, generate auth URL.
    Frontend opens URL in popup — callback is captured automatically.
    """
    global _auth_in_progress
    repo = ConfigRepo(db)
    app_id    = await repo.get("app_id")
    secret_id = await repo.get("secret_id")

    if not app_id or not secret_id:
        raise HTTPException(400, "Save App ID and Secret ID first.")

    redirect_uri = await repo.get("redirect_uri") or ""

    # Auto-detect: if RENDER_EXTERNAL_URL is set (Render sets this automatically),
    # use it as the redirect URI so user doesn't have to configure anything
    if not redirect_uri:
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
        if render_url:
            redirect_uri = f"{render_url}/api/auth/callback"
            await repo.set("redirect_uri", redirect_uri)
            logger.info(f"Auto-detected Render URL: {redirect_uri}")

    auth = FyersAuth(app_id=app_id, secret_id=secret_id, redirect_uri=redirect_uri)
    using_local = not redirect_uri

    if using_local:
        def on_code(auth_code: str):
            if auth_code:
                asyncio.run(_handle_auth_code(auth_code, app_id, secret_id, redirect_uri))
        ok = start_local_callback_server(on_code)
        if not ok:
            raise HTTPException(500, "Port 8765 is in use. Please close other instances and retry.")

    url = auth.get_auth_url()
    _auth_in_progress = True
    await repo.set("auth_status", "login_in_progress")

    effective_uri = redirect_uri or FyersAuth.LOCAL_URI
    return {"login_url": url, "redirect_uri": effective_uri, "using_local": using_local}

@app.get("/api/auth/callback")
async def auth_callback_hosted(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Used when hosted on Render/cloud — Fyers redirects here with auth_code.
    Set redirect_uri in Broker tab to: https://your-app.onrender.com/api/auth/callback
    """
    params     = dict(request.query_params)
    auth_code  = params.get("auth_code") or params.get("code")
    s_val      = params.get("s") or params.get("status") or "ok"

    if not auth_code or s_val == "error":
        return HTMLResponse(_cb_html("error", "❌ Login Failed", "Auth code not received."), status_code=400)

    repo      = ConfigRepo(db)
    app_id    = await repo.get("app_id")
    secret_id = await repo.get("secret_id")
    ruri = await repo.get("redirect_uri") or ""
    if not ruri:
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
        if render_url:
            ruri = f"{render_url}/api/auth/callback"

    if not app_id or not secret_id:
        return HTMLResponse(_cb_html("error", "❌ Not Configured", "Broker credentials missing."), status_code=400)

    auth  = FyersAuth(app_id=app_id, secret_id=secret_id, redirect_uri=ruri)
    token = await auth.exchange_code(auth_code)

    if not token:
        return HTMLResponse(_cb_html("error", "❌ Token Exchange Failed", "Could not get access token from Fyers."), status_code=400)

    await repo.set("access_token", token)
    await repo.set("auth_status",  "authenticated")
    await repo.set("auth_time",    datetime.now().isoformat())
    logger.info("✅ Fyers auth via hosted callback successful.")

    return HTMLResponse(_cb_html("success", "✅ Login Successful!", "Session created. This window will close automatically."))


def _cb_html(status, title, body):
    color = "#4ade80" if status == "success" else "#f87171"
    bg    = "#052e16" if status == "success" else "#2d0000"
    bd    = "#16a34a" if status == "success" else "#dc2626"
    return f"""<!DOCTYPE html><html><head><title>Fyers Auth</title>
<style>body{{margin:0;background:#0a0e1a;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:'Segoe UI',sans-serif}}
.b{{background:{bg};border:1px solid {bd};border-radius:16px;padding:40px 60px;text-align:center}}
h2{{color:{color};margin-bottom:12px}}p{{color:#e2e8f0;font-size:15px;margin-bottom:20px}}
button{{background:{color};color:#000;border:none;border-radius:8px;padding:10px 24px;font-size:14px;font-weight:700;cursor:pointer}}</style>
</head><body><div class="b"><h2>{title}</h2><p>{body}</p><button onclick="window.close()">Close Window</button></div>
<script>
if(window.opener){{window.opener.postMessage(JSON.stringify({{type:'fyers_auth',status:'{status}'}}),'*');}};
setTimeout(()=>window.close(),2500);
</script></body></html>"""




async def _handle_auth_code(auth_code: str, app_id: str, secret_id: str, redirect_uri: str = ''):
    """Called automatically when Fyers redirects with auth_code."""
    global _auth_in_progress
    try:
        auth = FyersAuth(app_id=app_id, secret_id=secret_id, redirect_uri=redirect_uri)
        access_token = await auth.exchange_code(auth_code)

        async with AsyncSessionLocal() as db:
            repo = ConfigRepo(db)
            if access_token:
                await repo.set("access_token", access_token)
                await repo.set("auth_status", "authenticated")
                await repo.set("auth_time", datetime.now().isoformat())
                logger.info("✅ Fyers authentication successful.")
            else:
                await repo.set("auth_status", "token_exchange_failed")
                logger.error("❌ Token exchange failed.")
    except Exception as e:
        logger.error(f"Auth handler error: {e}")
    finally:
        _auth_in_progress = False
        stop_local_callback_server()


@app.get("/api/auth/status")
async def auth_status(db: AsyncSession = Depends(get_db)):
    repo = ConfigRepo(db)
    app_id       = await repo.get("app_id")
    secret_id    = await repo.get("secret_id")
    access_token = await repo.get("access_token")
    status       = await repo.get("auth_status") or "not_configured"
    auth_time    = await repo.get("auth_time")
    has_token    = bool(access_token)
    token_display = ("***" + access_token[-6:]) if has_token and len(access_token) > 6 else ""
    return {
        "has_credentials": bool(app_id and secret_id),
        "has_token":       has_token,
        "status":          status,
        "app_id":          app_id or "",
        "auth_time":       auth_time,
        "token_preview":   token_display,
        "login_in_progress": _auth_in_progress,
        "redirect_uri":     await repo.get("redirect_uri") or "",
    }


@app.post("/api/auth/logout")
async def logout(db: AsyncSession = Depends(get_db)):
    repo = ConfigRepo(db)
    await repo.set("access_token", "")
    await repo.set("auth_status", "logged_out")
    stop_local_callback_server()
    return {"status": "logged_out"}

@app.get("/api/auth/redirect-uri")
async def get_redirect_uri(db: AsyncSession = Depends(get_db)):
    """Returns the exact redirect URI to register in Fyers app settings."""
    repo = ConfigRepo(db)
    saved = await repo.get("redirect_uri") or ""
    if not saved:
        render_url = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
        if render_url:
            saved = f"{render_url}/api/auth/callback"
    if not saved:
        saved = f"http://localhost:{FyersAuth.LOCAL_PORT}"
    return {"redirect_uri": saved}




# ══════════════════════════════════════════════════════════════════════════════
# TRADING CONTROL
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/trading/start")
async def start_trading(req: StartTradingRequest, background_tasks: BackgroundTasks,
                        db: AsyncSession = Depends(get_db)):
    if orchestrator.is_running:
        return {"status": "already_running"}

    repo = ConfigRepo(db)
    app_id       = await repo.get("app_id")
    access_token = await repo.get("access_token")
    secret_id    = await repo.get("secret_id")
    tg_token     = await repo.get("telegram_token") or ""
    tg_chat      = await repo.get("telegram_chat_id") or ""

    # Both real and paper mode require a valid token — paper still fetches live market data
    if not access_token:
        raise HTTPException(400, "Not authenticated. Please login via Broker tab first. Paper trade also needs live data from Fyers.")

    orchestrator.configure(
        client_id      = app_id,
        secret_key     = secret_id or "",
        access_token   = access_token,
        telegram_token = tg_token,
        telegram_chat  = tg_chat,
        lot_size       = req.lot_size,
        max_daily_loss = req.max_daily_loss,
        max_trades     = req.max_trades,
        scaling        = req.scaling_enabled,
        trade_mode     = req.trade_mode,
        nifty_enabled  = req.nifty_enabled,
        sensex_enabled = req.sensex_enabled,
    )

    ok = await orchestrator.initialize()
    if not ok:
        raise HTTPException(400, "Initialisation failed — token may be expired. Please re-login in Broker tab.")

    background_tasks.add_task(_run_trading)
    return {"status": "started", "mode": req.trade_mode}


async def _run_trading():
    try:
        await orchestrator.start()
    except Exception as e:
        logger.error(f"Trading error: {e}")


@app.post("/api/trading/stop")
async def stop_trading():
    orchestrator.stop()
    return {"status": "stopped"}


@app.get("/api/trading/status")
async def get_status():
    return orchestrator.get_status()


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/dashboard")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    status = orchestrator.get_status()
    repo   = TradeRepo(db)
    open_t = await repo.get_open_trades()
    today  = await repo.get_today_trades()
    today_pnl = sum(t.pnl or 0 for t in today if t.pnl)
    return {**status, "open_positions_count": len(open_t),
            "today_pnl": today_pnl, "today_trades_count": len(today)}


# ══════════════════════════════════════════════════════════════════════════════
# POSITIONS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/positions/open")
async def get_open_positions(db: AsyncSession = Depends(get_db)):
    repo   = TradeRepo(db)
    trades = await repo.get_open_trades()
    result = []
    for t in trades:
        # pick correct LTP based on index
        if "SENSEX" in t.symbol:
            ltp = orchestrator.sensex_ce_ltp if t.leg == "CE" else orchestrator.sensex_pe_ltp
        else:
            ltp = orchestrator.ce_ltp if t.leg == "CE" else orchestrator.pe_ltp
        pnl = (t.entry_price - ltp) * t.qty if ltp else 0
        st  = orchestrator.strategy.get_supertrend_info(t.leg) if orchestrator.strategy else {}
        result.append({
            "id": t.id, "symbol": t.symbol, "leg": t.leg, "qty": t.qty,
            "avg_price": t.entry_price, "ltp": ltp, "live_pnl": round(pnl, 2),
            "reentry_count": t.reentry_count,
            "entry_time": t.entry_time.isoformat() if t.entry_time else None,
            "supertrend_direction": st.get("direction", "unknown"),
            "st_value": st.get("value", 0),
            "is_paper": t.order_id == "PAPER"
        })
    return result


@app.get("/api/positions/today")
async def get_today_positions(db: AsyncSession = Depends(get_db)):
    repo   = TradeRepo(db)
    trades = await repo.get_today_trades()
    return [{"id": t.id, "symbol": t.symbol, "leg": t.leg, "qty": t.qty,
             "entry_price": t.entry_price, "exit_price": t.exit_price, "pnl": t.pnl,
             "status": t.status, "exit_reason": t.exit_reason,
             "is_paper": t.order_id == "PAPER",
             "entry_time": t.entry_time.isoformat() if t.entry_time else None,
             "exit_time":  t.exit_time.isoformat()  if t.exit_time  else None}
            for t in trades]


# ══════════════════════════════════════════════════════════════════════════════
# P&L
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/pnl/history")
async def get_pnl_history(db: AsyncSession = Depends(get_db)):
    repo = DailyPnLRepo(db)
    records = await repo.get_all()
    return [{"date": r.date.strftime("%Y-%m-%d"), "total_pnl": r.total_pnl,
             "total_trades": r.total_trades, "winning_trades": r.winning_trades,
             "losing_trades": r.losing_trades} for r in records]


@app.get("/api/pnl/trades")
async def get_all_trades(db: AsyncSession = Depends(get_db)):
    repo   = TradeRepo(db)
    trades = await repo.get_all_trades()
    return [{"id": t.id, "date": t.entry_time.strftime("%Y-%m-%d") if t.entry_time else None,
             "symbol": t.symbol, "leg": t.leg, "qty": t.qty,
             "entry_price": t.entry_price, "exit_price": t.exit_price,
             "pnl": t.pnl, "status": t.status, "exit_reason": t.exit_reason,
             "is_paper": t.order_id == "PAPER",
             "entry_time": t.entry_time.isoformat() if t.entry_time else None,
             "exit_time":  t.exit_time.isoformat()  if t.exit_time  else None}
            for t in trades]


# ══════════════════════════════════════════════════════════════════════════════
# SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/profile/telegram")
async def save_telegram(req: TelegramConfig, db: AsyncSession = Depends(get_db)):
    repo = ConfigRepo(db)
    await repo.set("telegram_token",   req.telegram_token)
    await repo.set("telegram_chat_id", req.telegram_chat_id)
    return {"status": "saved"}


@app.post("/api/profile/test-telegram")
async def test_telegram(db: AsyncSession = Depends(get_db)):
    repo    = ConfigRepo(db)
    token   = await repo.get("telegram_token")
    chat_id = await repo.get("telegram_chat_id")
    if not token or not chat_id:
        raise HTTPException(400, "Telegram not configured")
    svc = TelegramService(token, chat_id)
    ok  = await svc.test_connection()
    return {"success": ok}


@app.get("/api/profile")
async def get_profile(db: AsyncSession = Depends(get_db)):
    repo   = ConfigRepo(db)
    config = await repo.get_all()
    return {"app_id": config.get("app_id", ""),
            "telegram_token":   config.get("telegram_token", ""),
            "telegram_chat_id": config.get("telegram_chat_id", "")}


@app.post("/api/settings/risk")
async def update_risk(req: RiskSettingsRequest, db: AsyncSession = Depends(get_db)):
    repo = ConfigRepo(db)
    await repo.set("max_daily_loss",     str(req.max_daily_loss))
    await repo.set("max_trades_per_day", str(req.max_trades_per_day))
    await repo.set("lot_size",           str(req.lot_size))
    await repo.set("scaling_enabled",    str(req.scaling_enabled))
    if orchestrator.strategy:
        orchestrator.strategy.max_daily_loss  = req.max_daily_loss
        orchestrator.strategy.max_trades      = req.max_trades_per_day
        orchestrator.strategy.scaling_enabled = req.scaling_enabled
    return {"status": "updated"}


@app.get("/api/settings/risk")
async def get_risk_settings(db: AsyncSession = Depends(get_db)):
    repo   = ConfigRepo(db)
    config = await repo.get_all()
    return {"max_daily_loss":     float(config.get("max_daily_loss",     10000)),
            "max_trades_per_day":  int(config.get("max_trades_per_day",  20)),
            "lot_size":            int(config.get("lot_size",             50)),
            "scaling_enabled":     config.get("scaling_enabled", "True") == "True"}


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
