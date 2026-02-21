import hashlib
import logging
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional, Callable
import httpx

logger = logging.getLogger(__name__)
FYERS_API_URL = "https://api-t1.fyers.in/api/v3"

_auth_server: Optional[HTTPServer] = None


class _CallbackHandler(BaseHTTPRequestHandler):
    on_code: Optional[Callable] = None

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        auth_code = (params.get("auth_code") or params.get("code") or [None])[0]
        s_val     = (params.get("s") or ["ok"])[0]
        ok = bool(auth_code and s_val != "error")
        html = _page("success" if ok else "error",
                     "✅ Login Successful!" if ok else "❌ Login Failed",
                     "Session created. This window will close." if ok else "Please try again.")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())
        if self.on_code:
            threading.Thread(target=self.on_code, args=(auth_code if ok else None,), daemon=True).start()

    def log_message(self, *args):
        pass


def _page(status, title, body):
    c = "#4ade80" if status == "success" else "#f87171"
    b = "#052e16" if status == "success" else "#2d0000"
    d = "#16a34a" if status == "success" else "#dc2626"
    return f"""<!DOCTYPE html><html><head><title>Fyers Auth</title>
<style>body{{margin:0;background:#0a0e1a;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:'Segoe UI',sans-serif}}
.b{{background:{b};border:1px solid {d};border-radius:16px;padding:40px 60px;text-align:center}}
h2{{color:{c};margin-bottom:12px}}p{{color:#e2e8f0;margin-bottom:20px}}
button{{background:{c};color:#000;border:none;border-radius:8px;padding:10px 24px;font-weight:700;cursor:pointer}}</style>
</head><body><div class="b"><h2>{title}</h2><p>{body}</p><button onclick="window.close()">Close</button></div>
<script>if(window.opener)window.opener.postMessage(JSON.stringify({{type:'fyers_auth',status:'{status}'}}),'*');
setTimeout(()=>window.close(),2500);</script></body></html>"""


class FyersAuth:
    LOCAL_PORT = 8765
    LOCAL_URI  = f"http://localhost:{LOCAL_PORT}"

    def __init__(self, app_id="", secret_id="", redirect_uri=""):
        self.app_id       = app_id
        self.secret_id    = secret_id
        self.redirect_uri = redirect_uri.rstrip("/") if redirect_uri else self.LOCAL_URI

    def get_auth_url(self) -> str:
        # Lazy import — fyers_apiv3 only loaded when user actually clicks Login
        try:
            from fyers_apiv3 import fyersModel  # noqa
            session = fyersModel.SessionModel(
                client_id=self.app_id, secret_key=self.secret_id,
                redirect_uri=self.redirect_uri, response_type="code",
                grant_type="authorization_code", state="trading_bot"
            )
            return session.generate_authcode()
        except Exception as e:
            raise Exception(f"Could not generate Fyers login URL: {e}")

    async def exchange_code(self, auth_code: str) -> Optional[str]:
        try:
            from fyers_apiv3 import fyersModel  # noqa — lazy import
            session = fyersModel.SessionModel(
                client_id=self.app_id, secret_key=self.secret_id,
                redirect_uri=self.redirect_uri, response_type="code",
                grant_type="authorization_code"
            )
            session.set_token(auth_code)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, session.generate_token)
            logger.info(f"Token response: {response}")
            if response.get("s") == "ok":
                return response.get("access_token")
            logger.error(f"Token exchange failed: {response}")
            return None
        except Exception as e:
            logger.error(f"Token exchange error: {e}")
            return None

    async def validate_token(self, client_id: str, access_token: str) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{FYERS_API_URL}/profile",
                                     headers={"Authorization": f"{client_id}:{access_token}"},
                                     timeout=10)
                return r.status_code == 200
        except Exception:
            return False


def start_local_callback_server(on_code: Callable) -> bool:
    global _auth_server
    try:
        stop_local_callback_server()
        class Handler(_CallbackHandler): pass
        Handler.on_code = on_code
        _auth_server = HTTPServer(("0.0.0.0", FyersAuth.LOCAL_PORT), Handler)
        threading.Thread(target=_auth_server.serve_forever, daemon=True).start()
        logger.info(f"Callback server on port {FyersAuth.LOCAL_PORT}")
        return True
    except OSError as e:
        logger.error(f"Callback server error: {e}")
        return False


def stop_local_callback_server():
    global _auth_server
    if _auth_server:
        try: _auth_server.shutdown()
        except Exception: pass
        _auth_server = None
