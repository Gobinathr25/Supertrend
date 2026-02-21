"""Startup wrapper with full error reporting for Render."""
import sys
import os
import traceback

print("=" * 50)
print("NIFTY Options Bot — Starting")
print(f"Python: {sys.version}")
print(f"CWD: {os.getcwd()}")
print(f"PORT env: {os.environ.get('PORT', 'not set')}")
print("=" * 50)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("\n[1/6] config.settings...")
    from config.settings import settings
    print("  OK")

    print("[2/6] database.models...")
    from database.models import init_db, get_db, AsyncSessionLocal, DB_PATH
    print(f"  OK — DB at: {DB_PATH}")

    print("[3/6] database.operations...")
    from database.operations import TradeRepo, DailyPnLRepo, ConfigRepo, LogRepo, ReentryRepo
    print("  OK")

    print("[4/6] notifications.service...")
    from notifications.service import TelegramService
    print("  OK")

    print("[5/6] services...")
    from services.fyers_auth import FyersAuth, start_local_callback_server, stop_local_callback_server
    from services.fyers_service import FyersService, ATMCalculator
    from services.order_service import OrderService
    from services.orchestrator import orchestrator
    print("  OK")

    print("[6/6] main app...")
    import main
    print("  OK")

    print("\n✅ All imports successful — launching uvicorn\n")

except Exception:
    print("\n❌ STARTUP FAILED:")
    traceback.print_exc()
    sys.exit(1)

import uvicorn
port = int(os.environ.get("PORT", 8000))
print(f"Starting on 0.0.0.0:{port}")
uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
